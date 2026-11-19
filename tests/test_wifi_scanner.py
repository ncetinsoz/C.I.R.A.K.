import os
import pytest
from cirak.backend.wifi_scanner import WiFiScanner, WiFiScanReport
from cirak.backend.snmp_client import SNMPClient, SNMPSwitchReport
from cirak.backend.arp_conflict import ARPConflictDetector, ARPConflictReport


def test_wifi_scanner_simulation():
    scanner = WiFiScanner(simulate=True)
    report = scanner.scan()

    assert isinstance(report, WiFiScanReport)
    assert report.total_aps >= 5
    assert report.count_24ghz >= 1
    assert report.count_5ghz >= 1
    assert report.best_24ghz_channel in (1, 6, 11)
    assert report.connected_ssid == "DEU-Ogrenci"

    # Check AP structure
    ap0 = report.access_points[0]
    assert ap0.ssid != ""
    assert ":" in ap0.bssid
    assert ap0.signal_dbm < 0
    assert ap0.band in ("2.4 GHz", "5 GHz")


def test_wifi_connect_eduroam_8021x_and_wpa2():
    scanner = WiFiScanner(simulate=True)

    # 1. DEÜ eduroam 802.1X EAP-TTLS + Phase 2 PAP (No external CA certificate required)
    ok_edu, msg_edu = scanner.connect_network(
        ssid="eduroam",
        auth_mode="eap",
        identity="ad.soyad@deu.edu.tr",
        password="secretPassword123",
        eap_method="ttls",
        phase2_auth="pap",
    )
    assert ok_edu is True
    assert "eduroam" in msg_edu
    assert "802.1X" in msg_edu

    # 2. Missing identity or password for 802.1X must fail cleanly
    ok_fail, msg_fail = scanner.connect_network(
        ssid="eduroam",
        auth_mode="eap",
        identity="",
        password="",
    )
    assert ok_fail is False

    # 3. WPA2-PSK connection
    ok_psk, msg_psk = scanner.connect_network(
        ssid="DEU-Lab-WiFi",
        auth_mode="psk",
        password="StrongPassword2026",
    )
    assert ok_psk is True
    assert "DEU-Lab-WiFi" in msg_psk

    # 4. Active AP telemetry in simulation mode
    ap_info = scanner.get_active_ap_telemetry()
    assert ap_info is not None
    assert ap_info["ssid"] == "eduroam"
    assert ":" in ap_info["bssid"]


def test_snmp_client_asn1_ber_and_switch_inspection():
    # Verify pure-Python ASN.1 BER OID roundtrip encoding/decoding
    oid = "1.3.6.1.2.1.1.5.0"
    encoded = SNMPClient._encode_oid(oid)
    decoded = SNMPClient._decode_oid(encoded[2:])
    assert decoded == oid

    # Verify simulated SNMP switch port & sensor query
    client = SNMPClient(target_ip="194.27.65.2", community="public", simulate=True)
    rep = client.query_switch()
    assert isinstance(rep, SNMPSwitchReport)
    assert rep.reachable is True
    assert "DEU" in rep.sys_name
    assert rep.temperature_c is not None and rep.temperature_c > 0
    assert rep.cpu_load_pct is not None
    assert rep.total_ports >= 6
    assert rep.up_ports >= 1
    assert rep.down_ports >= 1
    assert rep.admin_down_ports >= 1


def test_arp_conflict_and_probe_detector():
    # Verify raw RFC 5227 ARP Probe frame construction (42 bytes Ethernet + ARP)
    frame = ARPConflictDetector.build_arp_request(
        src_mac=b"\xb8\x27\xeb\x11\x22\x33",
        sender_ip="0.0.0.0",
        target_ip="194.27.65.131",
    )
    assert len(frame) == 42
    assert frame[12:14] == b"\x08\x06"  # EtherType ARP

    # Verify simulated ARP conflict report
    det_clean = ARPConflictDetector(simulate=True)
    rep_clean = det_clean.run_scan()
    assert isinstance(rep_clean, ARPConflictReport)
    assert rep_clean.has_conflict is False
    assert rep_clean.arp_probes_captured >= 1


def test_v040_dialogs_and_advanced_discovery_view():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QThreadPool
    from PySide6.QtWidgets import QApplication
    from cirak.gui.dialogs.wifi_connect_dialog import WiFiConnectDialog
    from cirak.gui.dialogs.snmp_switch_dialog import SwitchSNMPDialog
    from cirak.gui.views.rogue_dhcp_view import RogueDHCPView

    app = QApplication.instance() or QApplication([])
    assert app is not None

    # 1. WiFiConnectDialog defaults to DEÜ eduroam 802.1X EAP-TTLS + PAP
    wifi_dlg = WiFiConnectDialog(initial_ssid="eduroam", initial_security="WPA2-Enterprise (802.1X)")
    assert wifi_dlg.auth_mode == "eap"
    assert wifi_dlg.eap_method == "ttls"
    assert wifi_dlg.phase2_auth == "pap"

    # 2. SwitchSNMPDialog filter buttons and simulated port table population
    snmp_dlg = SwitchSNMPDialog(initial_ip="194.27.65.2", initial_community="public", auto_query=False)
    sim_report = SNMPClient(target_ip="194.27.65.2", community="public", simulate=True).query_switch()
    snmp_dlg._on_query_finished(sim_report)
    assert snmp_dlg.table.rowCount() == sim_report.total_ports
    snmp_dlg._set_port_filter("ADMIN-DOWN")
    assert snmp_dlg.table.rowCount() == sim_report.admin_down_ports

    # 3. Upgraded RogueDHCPView ("İleri Keşif") 3 cards
    adv_view = RogueDHCPView()
    assert adv_view.rogue_card is not None
    assert adv_view.arp_card is not None
    assert adv_view.snmp_card is not None
    wifi_dlg.close()
    snmp_dlg.close()
    adv_view.close()
    QThreadPool.globalInstance().waitForDone(3000)
    app.processEvents()
