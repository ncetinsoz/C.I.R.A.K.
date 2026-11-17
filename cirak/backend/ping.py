"""
Layer 3: Gateway Ping & ARP Resolution test.
Pings the real default gateway, measures round-trip time (RTT) and packet loss,
and discovers the gateway hardware MAC address from the kernel ARP table.
"""

from pathlib import Path
import re
import subprocess
import time
from typing import Optional
from cirak.backend.base import BaseTest
from cirak.backend.network_detector import NetworkDetector
from cirak.core.models import TestResult, TestStatus, PingResult


class PingTest(BaseTest):
    """Diagnoses default gateway latency and L2 ARP connectivity."""

    def __init__(
        self,
        target_ip: Optional[str] = None,
        interface: Optional[str] = None,
        count: int = 4,
        timeout_sec: float = 2.0,
        simulate: bool = False,
    ):
        iface = interface or NetworkDetector.get_active_interface()
        super().__init__(name="4. Gateway Ping", interface=iface, simulate=simulate)
        self.target_ip = target_ip
        self.count = count
        self.timeout_sec = timeout_sec

    def get_default_gateway(self) -> Optional[str]:
        if self.target_ip:
            return self.target_ip

        if self.simulate:
            return "10.20.102.1"

        gw_info = NetworkDetector.get_default_gateway()
        if gw_info:
            return gw_info["gateway"]

        return None

    def get_mac_from_arp(self, ip: str) -> str:
        if self.simulate:
            return "00:0c:29:84:a1:fe"

        mac = NetworkDetector.get_gateway_mac(ip)
        return mac or "Bilinmiyor"

    def run(self) -> TestResult:
        """Execute ping test."""
        start_time = time.time()
        gateway = self.get_default_gateway()

        if not gateway:
            return self._create_result(
                status=TestStatus.FAILED,
                start_time=start_time,
                summary="Ağ Geçidi (Gateway) Bulunamadı",
                details={"error": "No default route in kernel routing table"}
            )

        if self.simulate:
            mac = self.get_mac_from_arp(gateway)
            summary = f"Gateway: {gateway} | RTT: 0.8 ms | MAC: {mac}"
            return self._create_result(
                status=TestStatus.PASSED,
                start_time=start_time,
                summary=summary,
                details={
                    "gateway": gateway,
                    "latency_ms": 0.8,
                    "packet_loss_pct": 0.0,
                    "mac": mac,
                }
            )

        # Run system ping bound to target interface to prevent routing via wrong interface
        cmd = ["ping"]
        if self.interface and self.interface != "lo":
            cmd += ["-I", self.interface]
        cmd += ["-c", str(self.count), "-W", str(int(self.timeout_sec)), gateway]

        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            if res.returncode != 0 and "-I" in cmd:
                # Fallback without -I in case capability or interface name restricts it
                fallback_cmd = ["ping", "-c", str(self.count), "-W", str(int(self.timeout_sec)), gateway]
                res = subprocess.run(fallback_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)

            output = res.stdout

            loss_match = re.search(r"(\d+(?:\.\d+)?)%\s*packet loss", output)
            loss_pct = float(loss_match.group(1)) if loss_match else 100.0

            rtt_match = re.search(r"rtt min/avg/max/mdev = [\d\.]+/([\d\.]+)/", output)
            avg_rtt = float(rtt_match.group(1)) if rtt_match else 0.0

            mac = self.get_mac_from_arp(gateway)

            if loss_pct < 100.0 and res.returncode == 0:
                summary = f"Gateway: {gateway} | RTT: {avg_rtt:.1f} ms | MAC: {mac}"
                return self._create_result(
                    status=TestStatus.PASSED,
                    start_time=start_time,
                    summary=summary,
                    details={
                        "gateway": gateway,
                        "latency_ms": avg_rtt,
                        "packet_loss_pct": loss_pct,
                        "mac": mac,
                    }
                )
            else:
                return self._create_result(
                    status=TestStatus.FAILED,
                    start_time=start_time,
                    summary=f"Ağ geçidi yanıt vermedi (%{loss_pct:.0f} kayıp)",
                    details={"gateway": gateway, "packet_loss_pct": loss_pct, "mac": mac}
                )
        except Exception as e:
            return self._create_result(
                status=TestStatus.FAILED,
                start_time=start_time,
                summary=f"Ping hatası: {str(e)}",
                details={"gateway": gateway, "error": str(e)}
            )
