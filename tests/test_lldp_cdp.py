"""
Tests for Layer 2 LLDP and CDP frame parsing.
"""

import struct
from cirak.backend.lldp_cdp import LLDPCdpTest
from cirak.core.models import TestStatus


def test_lldp_cdp_simulation():
    test = LLDPCdpTest(interface="eth0", simulate=True)
    res = test.run()

    assert res.status == TestStatus.PASSED
    assert res.details["system_name"] == "Catalyst-9300"
    assert res.details["port_id"] == "Gi1/0/24"
    assert res.details["vlan_id"] == 102
    assert "Catalyst-9300" in res.summary


def test_parse_lldp_synthetic_frame():
    test = LLDPCdpTest()

    # TLV 1: (1 << 9) | 7 = 0x0207
    tlv1_hdr = struct.pack("!H", (1 << 9) | 7)
    tlv1_val = b"\x04\x00\x11\x22\x33\x44\x55"

    # TLV 2: (2 << 9) | 5 = 0x0405
    tlv2_hdr = struct.pack("!H", (2 << 9) | 5)
    tlv2_val = b"\x01eth0"

    # TLV 5: (5 << 9) | 8 = 0x0a08
    tlv5_hdr = struct.pack("!H", (5 << 9) | 8)
    tlv5_val = b"Cisco-SW"

    # TLV 0: 0x0000
    tlv0 = b"\x00\x00"

    payload = tlv1_hdr + tlv1_val + tlv2_hdr + tlv2_val + tlv5_hdr + tlv5_val + tlv0
    parsed = test.parse_lldp_frame(payload)

    assert parsed is not None
    assert parsed.system_name == "Cisco-SW"
    assert parsed.chassis_id == "00:11:22:33:44:55"
    assert parsed.port_id == "eth0"


def test_parse_cdp_synthetic_frame():
    test = LLDPCdpTest()

    # 802.2 LLC + SNAP header for Cisco CDP (aa:aa:03:00:00:0c:20:00)
    llc_snap = b"\xaa\xaa\x03\x00\x00\x0c\x20\x00"
    # CDP header: version=2, ttl=180, checksum=0x0000
    cdp_hdr = struct.pack("!BBH", 2, 180, 0)

    # TLV 0x0001: Device ID ("DEU-SW-CORE1")
    dev_id = b"DEU-SW-CORE1"
    tlv_dev = struct.pack("!HH", 0x0001, 4 + len(dev_id)) + dev_id

    # TLV 0x0003: Port ID ("GigabitEthernet1/0/12")
    port_id = b"GigabitEthernet1/0/12"
    tlv_port = struct.pack("!HH", 0x0003, 4 + len(port_id)) + port_id

    # TLV 0x0006: Platform ("cisco WS-C2960X-24TS-L")
    platform = b"cisco WS-C2960X-24TS-L"
    tlv_plat = struct.pack("!HH", 0x0006, 4 + len(platform)) + platform

    # TLV 0x000A: Native VLAN (65)
    tlv_vlan = struct.pack("!HHH", 0x000A, 6, 65)

    payload = llc_snap + cdp_hdr + tlv_dev + tlv_port + tlv_plat + tlv_vlan
    parsed = test.parse_cdp_frame(payload, src_mac="94:33:d8:2a:01:ef")

    assert parsed is not None
    assert parsed.protocol == "CDP"
    assert parsed.system_name == "DEU-SW-CORE1"
    assert parsed.port_id == "GigabitEthernet1/0/12"
    assert parsed.system_description == "cisco WS-C2960X-24TS-L"
    assert parsed.vlan_id == 65
    assert parsed.vendor == "Cisco Systems"
    assert parsed.is_unauthorized_switch is False


def test_parse_eapol_nac_and_pvst_vlan():
    test = LLDPCdpTest(simulate=True)

    # 1. 802.1X EAPOL Request-Identity frame from Cisco switch port MAC (00:26:cb:11:22:33)
    eapol_payload = b"\x02\x00\x00\x05\x01\x01\x00\x05\x01"
    nac_info = test.parse_eapol_nac_frame(eapol_payload, src_mac="00:26:cb:11:22:33")
    assert nac_info is not None
    assert "802.1X NAC" in nac_info.protocol
    assert "Cisco" in nac_info.vendor
    assert "Standart Ağ Cihazı" not in nac_info.system_name

    # 2. Cisco PVST+ BPDU with trailing PVID TLV (00:00:00:02:00:66 -> VLAN 102)
    pvst_payload = (b"\xaa\xaa\x03\x00\x00\x0c\x01\x0b" + (b"\x00" * 35) + b"\x00\x00\x00\x02\x00\x66")
    stp_info = test.parse_stp_bpdu(pvst_payload, src_mac="94:33:d8:2a:01:ef", is_pvst=True)
    assert stp_info is not None
    assert stp_info.vlan_id == 102
    assert "PVST+" in stp_info.protocol
    assert "Cisco" in stp_info.vendor


def test_ignore_local_cirak_self_packets():
    from cirak.backend.network_detector import NetworkDetector

    assert NetworkDetector.is_local_device(system_name="cirak") is True
    assert NetworkDetector.is_local_device(system_name="CIRAK.local") is True
    assert NetworkDetector.is_local_device(system_name="DEU-SW-CORE1") is False

    test = LLDPCdpTest(simulate=True)
    # Build an Ethernet LLDP frame advertising 'cirak' (local host)
    dst_mac = b"\x01\x80\xc2\x00\x00\x0e"
    src_mac = b"\xdc\xa6\x32\x11\x22\x33"
    eth_type = struct.pack("!H", 0x88CC)
    tlv1 = struct.pack("!H", (1 << 9) | 7) + b"\x04\xdc\xa6\x32\x11\x22\x33"
    tlv2 = struct.pack("!H", (2 << 9) | 5) + b"\x05eth0"
    tlv5 = struct.pack("!H", (5 << 9) | 5) + b"cirak"
    tlv0 = b"\x00\x00"
    raw_pkt = dst_mac + src_mac + eth_type + tlv1 + tlv2 + tlv5 + tlv0

    res = test._process_raw_packet("eth0", raw_pkt)
    assert res is None


