"""
Tests for Layer 3 DHCP negotiation and Rogue DHCP detection.
"""

from cirak.backend.dhcp import DHCPTest
from cirak.core.models import TestStatus


def test_dhcp_simulation_authorized():
    test = DHCPTest(interface="eth0", approved_servers=["10.20.0.1"], simulate=True)
    res = test.run()

    assert res.status == TestStatus.PASSED
    assert res.details["offered_ip"] == "10.20.102.88"
    assert res.details["server_id"] == "10.20.0.1"
    assert res.details["is_rogue"] is False
    assert res.details["router"] == "10.20.102.1"


def test_dhcp_rogue_server_detection():
    # If approved_servers doesn't include the responding server (10.20.0.1), it should flag it as rogue
    test = DHCPTest(interface="eth0", approved_servers=["192.168.100.1"], simulate=True)
    # Inject rogue offer
    rogue_offer = test._get_simulated_rogue_offer()
    assert rogue_offer.is_rogue is True
    assert rogue_offer.server_id == "192.168.1.1"


def test_build_dhcp_discover():
    test = DHCPTest()
    pkt = test._build_dhcp_discover(0x12345678)
    assert len(pkt) >= 240
    # Magic cookie at offset 236
    assert pkt[236:240] == b"\x63\x82\x53\x63"
    # Option 53 (Discover) is at 240
    assert pkt[240:243] == b"\x35\x01\x01"
