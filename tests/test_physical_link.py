"""
Tests for Layer 1 Physical Link diagnostic test.
"""

from cirak.backend.physical_link import PhysicalLinkTest
from cirak.core.models import TestStatus


def test_physical_link_simulation():
    test = PhysicalLinkTest(interface="eth0", simulate=True)
    res = test.run()

    assert res.name == "1. Fiziksel Link"
    assert res.status == TestStatus.PASSED
    assert res.details["speed_mbps"] == 1000
    assert "Full Duplex" in res.details["duplex"]
    assert res.details["carrier"] is True
    assert res.details["interface"] == "eth0"


def test_physical_link_nonexistent_interface():
    test = PhysicalLinkTest(interface="nonexistent_eth99", simulate=False)
    res = test.run()

    assert res.name == "1. Fiziksel Link"
    assert res.status == TestStatus.FAILED
    assert "Kablo takılı değil veya link yok" in res.summary
