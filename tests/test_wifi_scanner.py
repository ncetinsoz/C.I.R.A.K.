import pytest
from cirak.backend.wifi_scanner import WiFiScanner, WiFiScanReport


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
