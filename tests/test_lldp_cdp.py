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
    assert "Switch: Catalyst-9300" in res.summary


def test_parse_lldp_synthetic_frame():
    test = LLDPCdpTest()

    # Construct synthetic LLDP packet payload:
    # TLV 1 (Chassis ID, type 1, len 7: subtype 4 + 6 MAC bytes)
    # TLV 2 (Port ID, type 2, len 6: subtype 1 + "eth0")
    # TLV 5 (System Name, type 5, len 8: "Cisco-SW")
    # TLV 0 (End, type 0, len 0)

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
