"""
Qt Signals for communication between background threads and PySide6 UI.
"""

from PySide6.QtCore import QObject, Signal


class NetworkSignals(QObject):
    """Signals for interface link and status changes."""
    link_changed = Signal(bool, int, str)  # connected, speed_mbps, duplex
    ip_changed = Signal(str, str)          # ip_address, interface
    wifi_status_changed = Signal(bool, str, int)  # connected, ssid, signal_pct
    quick_info_updated = Signal(str, str)  # switch_port_str, ip_str


class AutoTestSignals(QObject):
    """Signals for AutoTest L1-L7 chain runner."""
    step_started = Signal(int, str)       # step_index (0..5), step_name
    step_completed = Signal(int, object)  # step_index (0..5), TestResult
    progress_updated = Signal(int)        # percentage (0..100)
    test_finished = Signal(object)        # AutoTestReport


class DiscoverySignals(QObject):
    """Signals for network discovery (LLDP, ARP, Switch Blinker)."""
    lldp_received = Signal(object)         # LLDPInfo
    arp_device_found = Signal(object)      # ARPDevice
    arp_scan_finished = Signal(list)       # List[ARPDevice]
    blink_tick = Signal(bool)              # True (LED on) / False (LED off)
    blink_finished = Signal()


class RogueSignals(QObject):
    """Signals for Rogue DHCP Hunter."""
    server_detected = Signal(object)       # DHCPInfo
    rogue_alert = Signal(object)           # DHCPInfo
    scan_finished = Signal(list)           # List[DHCPInfo]
