"""
Tests for Layer 3 Ping and Gateway ARP test.
"""

from cirak.backend.ping import PingTest
from cirak.core.models import TestStatus


def test_ping_simulation():
    test = PingTest(target_ip="10.20.102.1", simulate=True)
    res = test.run()

    assert res.status == TestStatus.PASSED
    assert res.details["gateway"] == "10.20.102.1"
    assert res.details["mac"] == "00:0c:29:84:a1:fe"
    assert res.details["latency_ms"] == 0.8
    assert res.details["packet_loss_pct"] == 0.0


def test_ping_arp_mac_retrieval():
    test = PingTest(simulate=True)
    mac = test.get_mac_from_arp("10.20.102.1")
    assert mac == "00:0c:29:84:a1:fe"
