import pytest
from cirak.backend.speed_test import SpeedTestEngine, DualSpeedTestReport


def test_speed_test_simulation():
    engine = SpeedTestEngine(simulate=True)
    report = engine.run_test()

    assert isinstance(report, DualSpeedTestReport)
    assert report.internal.download_mbps > 50.0
    assert report.external.download_mbps > 30.0
    assert report.internal.latency_ms > 0
    assert report.external.latency_ms > 0
    assert report.internal.http_status == 200
    assert report.external.http_status == 200
    assert "DEÜ" in report.internal.target_name
    assert "Dış Ağ" in report.external.target_name
