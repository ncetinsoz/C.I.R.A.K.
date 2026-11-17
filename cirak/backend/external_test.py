"""
Layer 7: External Network & Internet Connectivity test.
Verifies WAN exit, NAT, firewall policy, and HTTP reachability (HTTP 200/204 OK).
"""

import time
import urllib.request
import urllib.error
from typing import Optional
from cirak.backend.base import BaseTest
from cirak.backend.network_detector import NetworkDetector
from cirak.core.models import TestResult, TestStatus, ExternalResult
from cirak import config


class ExternalTest(BaseTest):
    """Diagnoses WAN internet reachability and national academic network (ULAKBİM)."""

    def __init__(
        self,
        target_url: str = config.DEFAULT_EXTERNAL_URL,
        interface: Optional[str] = None,
        timeout_sec: float = 2.5,
        simulate: bool = False,
    ):
        iface = interface or NetworkDetector.get_active_interface()
        super().__init__(name="6. Dış Ağ (ULAKBIM)", interface=iface, simulate=simulate)
        self.target_url = target_url
        self.timeout_sec = timeout_sec

    def run(self) -> TestResult:
        """Execute real HTTP probe."""
        start_time = time.time()

        if self.simulate:
            summary = "HTTP GET: 200 OK | Kayıp: %0 (4/4 Paket) | 11.4 ms"
            return self._create_result(
                status=TestStatus.PASSED,
                start_time=start_time,
                summary=summary,
                details={
                    "target_url": self.target_url,
                    "http_status": 200,
                    "latency_ms": 11.4,
                    "is_online": True,
                }
            )

        # Real HTTP probe
        urls_to_try = [self.target_url, "http://www.google.com", config.ULAKBIM_EXTERNAL_URL]
        last_error = ""

        for url in urls_to_try:
            try:
                t0 = time.perf_counter()
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "CIRAK-Handheld-Tester/1.0"}
                )
                with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                    status_code = resp.getcode()
                    latency_ms = (time.perf_counter() - t0) * 1000.0

                if status_code in (200, 204, 301, 302):
                    summary = f"HTTP GET: {status_code} OK | {latency_ms:.1f} ms"
                    return self._create_result(
                        status=TestStatus.PASSED,
                        start_time=start_time,
                        summary=summary,
                        details={
                            "target_url": url,
                            "http_status": status_code,
                            "latency_ms": round(latency_ms, 2),
                            "is_online": True,
                        }
                    )
            except Exception as e:
                last_error = str(e)
                continue

        return self._create_result(
            status=TestStatus.FAILED,
            start_time=start_time,
            summary=f"Dış ağa erişilemedi: {last_error}",
            details={"error": last_error, "is_online": False}
        )
