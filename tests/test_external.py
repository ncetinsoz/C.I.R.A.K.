"""
Tests for Layer 7 External / ULAKBİM network test.
"""

from cirak.backend.external_test import ExternalTest
from cirak.core.models import TestStatus


def test_external_simulation():
    test = ExternalTest(target_url="http://ulakbim.tubitak.gov.tr", simulate=True)
    res = test.run()

    assert res.status == TestStatus.PASSED
    assert res.details["http_status"] == 200
    assert res.details["latency_ms"] == 11.4
    assert res.details["is_online"] is True
    assert "200 OK" in res.summary
