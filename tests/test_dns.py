"""
Tests for Layer 7 DNS resolution test.
"""

from cirak.backend.dns_test import DNSTest
from cirak.core.models import TestStatus


def test_dns_simulation():
    test = DNSTest(domain="kampus.edu.tr", simulate=True)
    res = test.run()

    assert res.status == TestStatus.PASSED
    assert res.details["domain"] == "kampus.edu.tr"
    assert res.details["resolved_ip"] == "10.20.5.15"
    assert res.details["latency_ms"] == 4.2
    assert "kampus.edu.tr" in res.summary


def test_dns_resolv_conf_fallback():
    test = DNSTest(simulate=False)
    servers = test.get_configured_dns_servers()
    assert isinstance(servers, list)
    assert len(servers) > 0
