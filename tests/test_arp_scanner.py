"""
Tests for Subnet ARP Scanner and vendor detection.
"""

from cirak.backend.arp_scanner import ARPScanner


def test_arp_scanner_simulation():
    scanner = ARPScanner(simulate=True)
    devices = scanner.scan_subnet()

    assert len(devices) >= 5
    ips = [d.ip for d in devices]
    assert "10.20.102.1" in ips
    assert "10.20.102.45" in ips

    # Check vendor assignment
    vendors = {d.ip: d.vendor for d in devices}
    assert "Cisco" in vendors["10.20.102.1"]
    assert "Raspberry Pi" in vendors["10.20.102.45"]
