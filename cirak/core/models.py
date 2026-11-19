"""
Data models and status enums for Ç.I.R.A.K. network analyzer.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import time


class TestStatus(str, Enum):
    """Execution status for a diagnostic test step."""
    __test__ = False
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    WARNING = "WARNING"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class TestResult:
    """General result object for any diagnostic test step."""
    __test__ = False
    name: str
    status: TestStatus = TestStatus.PENDING
    duration_ms: float = 0.0
    summary: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    @property
    def is_success(self) -> bool:
        return self.status == TestStatus.PASSED


@dataclass
class PhysicalLinkInfo:
    """Layer 1: Physical Link and PHY status."""
    connected: bool = False
    speed_mbps: int = 0
    duplex: str = "Unknown"  # "Full", "Half", "Unknown"
    mdix: str = "Auto"       # "Straight", "Crossover", "Auto"
    carrier: bool = False
    rx_bytes: int = 0
    tx_bytes: int = 0
    rx_packets: int = 0
    tx_packets: int = 0
    interface: str = "eth0"
    mac_address: str = ""


@dataclass
class LLDPInfo:
    """Layer 2: LLDP / CDP / L2 Switch neighbor discovery info."""
    chassis_id: str = ""
    system_name: str = ""
    system_description: str = ""
    software_version: str = ""
    port_id: str = ""
    port_description: str = ""
    vlan_id: Optional[int] = None
    vlan_name: str = ""
    management_ip: str = ""
    ttl: int = 120
    protocol: str = "CDP/LLDP"  # "CDP", "LLDP", "STP-BPDU", or "L2-ARP"
    vendor: str = ""
    capabilities: str = ""
    is_unauthorized_switch: bool = False
    received_at: float = field(default_factory=time.time)



@dataclass
class DHCPInfo:
    """Layer 3: DHCP negotiation & response details."""
    offered_ip: str = ""
    subnet_mask: str = ""
    router: str = ""
    dns_servers: List[str] = field(default_factory=list)
    domain_name: str = ""
    lease_time_sec: int = 0
    server_id: str = ""
    server_mac: str = ""
    response_time_ms: float = 0.0
    is_rogue: bool = False
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PingResult:
    """Layer 3: Ping / Gateway reachability."""
    target: str = ""
    is_reachable: bool = False
    latency_ms: float = 0.0
    packet_loss_pct: float = 0.0
    packets_sent: int = 4
    packets_received: int = 0
    mac_address: str = ""


@dataclass
class DNSResult:
    """Layer 7: Domain Name System resolution."""
    domain: str = ""
    is_resolved: bool = False
    resolved_ip: str = ""
    query_time_ms: float = 0.0
    dns_server_used: str = ""
    error_message: str = ""


@dataclass
class ExternalResult:
    """Layer 7: WAN / External (ULAKBIM) reachability."""
    target_url: str = ""
    is_online: bool = False
    http_status: int = 0
    latency_ms: float = 0.0
    packet_loss_pct: float = 0.0
    summary: str = ""


@dataclass
class AutoTestReport:
    """Consolidated report for the 6-step L1-L7 AutoTest."""
    overall_passed: bool = False
    total_duration_ms: float = 0.0
    steps: List[TestResult] = field(default_factory=list)
    completed_steps_count: int = 0
    total_steps_count: int = 6

    @property
    def passed_count(self) -> int:
        return sum(1 for s in self.steps if s.status == TestStatus.PASSED)


@dataclass
class ARPDevice:
    """Discovered network host in ARP sweep."""
    ip: str
    mac: str
    vendor: str = ""
    response_time_ms: float = 0.0


@dataclass
class WiFiNetwork:
    """Discovered wireless access point."""
    ssid: str
    bssid: str
    signal_level_dbm: int = -100
    signal_quality_pct: int = 0
    channel: int = 0
    security: str = "WPA2"
    connected: bool = False
