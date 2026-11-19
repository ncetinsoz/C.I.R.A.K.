"""
Tests for SettingsManager: DHCP/Static IP, VLAN 802.1Q, MAC spoofing, NTP sync, and cybersecurity validation.
"""

from pathlib import Path
from cirak.backend.settings_manager import SettingsManager


def test_settings_validation_and_persistence(tmp_path: Path):
    cfg_file = tmp_path / "settings.json"
    mgr = SettingsManager(settings_path=cfg_file, simulate=True)

    # Default NTP server must be time.deu.edu.tr
    assert mgr.settings.ntp_server == "time.deu.edu.tr"

    # Validations
    assert mgr.validate_ipv4("194.27.65.131") is True
    assert mgr.validate_ipv4("999.1.1.1") is False
    assert mgr.validate_ipv4("194.27.65.131; rm -rf /") is False

    assert mgr.validate_vlan(100) is True
    assert mgr.validate_vlan(0) is False
    assert mgr.validate_vlan(4095) is False

    # Unicast vs Multicast MAC validation
    assert mgr.validate_mac("b8:27:eb:12:34:56") is True
    assert mgr.validate_mac("01:00:0c:cc:cc:cc") is False  # Multicast bit set!
    assert mgr.validate_mac("00:00:00:00:00:00") is False

    assert mgr.validate_hostname("time.deu.edu.tr") is True
    assert mgr.validate_hostname("time.deu.edu.tr && whoami") is False

    # Apply static IP + VLAN in simulation mode
    mgr.settings.ip_mode = "static"
    mgr.settings.static_ip = "194.27.65.131"
    mgr.settings.subnet_prefix = 24
    mgr.settings.gateway = "194.27.65.1"
    mgr.settings.vlan_enabled = True
    mgr.settings.vlan_id = 65
    ok, msg = mgr.apply_network_config("eth0")
    assert ok is True
    assert cfg_file.exists()

    # Sync NTP in simulation mode
    ok_ntp, msg_ntp = mgr.sync_ntp_time("time.deu.edu.tr")
    assert ok_ntp is True
    assert "time.deu.edu.tr" in msg_ntp


def test_system_info_and_tactile_settings_widgets():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from cirak.gui.views.settings_view import SystemInfoDialog, SettingsView

    app = QApplication.instance() or QApplication([])
    assert app is not None

    specs = SystemInfoDialog.collect_system_specs()
    assert "0.4.0" in specs["sw_version"]
    assert specs["hw_model"] != ""
    assert specs["ram_info"] != ""
    assert specs["disk_info"] != ""
    assert specs["os_kernel"] != ""

    view = SettingsView()

    # Verify tactile VLAN and MAC toggle buttons work cleanly
    assert view.chk_vlan.isCheckable() is True
    view.chk_vlan.setChecked(True)
    assert view.chk_vlan.isChecked() is True
    assert "AKTİF" in view.chk_vlan.text()

    view.chk_mac.setChecked(True)
    assert view.chk_mac.isChecked() is True
    assert "AKTİF" in view.chk_mac.text()
    view.clock_timer.stop()
    view.close()


