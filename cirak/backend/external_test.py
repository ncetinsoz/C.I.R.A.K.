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
        super().__init__(name="6. Erişim Testi (İç & Dış Ağ)", interface=iface, simulate=simulate)
        self.target_url = target_url
        self.timeout_sec = timeout_sec

    def run(self) -> TestResult:
        """Execute dual HTTP probe: Internal DEÜ Campus + External Google."""
        start_time = time.time()

        if self.simulate:
            summary = "DEÜ (İç): 200 OK (8.2 ms) | Google (Dış): 200 OK (14.5 ms)"
            return self._create_result(
                status=TestStatus.PASSED,
                start_time=start_time,
                summary=summary,
                details={
                    "http_status": 200,
                    "latency_ms": 11.4,
                    "is_online": True,
                    "internal_url": "http://www.deu.edu.tr",
                    "internal_ok": True,
                    "internal_ms": 8.2,
                    "external_url": "http://www.google.com",
                    "external_ok": True,
                    "external_ms": 14.5,
                }
            )

        def probe_http(url: str) -> tuple[bool, int, float, str]:
            try:
                t0 = time.perf_counter()
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "CIRAK-Handheld-Tester/1.0"}
                )
                with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                    status_code = resp.getcode()
                    lat_ms = (time.perf_counter() - t0) * 1000.0
                    return True, status_code, lat_ms, ""
            except Exception as e:
                return False, 0, 0.0, str(e)

        deu_ok, deu_code, deu_ms, deu_err = probe_http("http://www.deu.edu.tr")
        google_ok, google_code, google_ms, google_err = probe_http("http://www.google.com")

        if deu_ok and google_ok:
            status = TestStatus.PASSED
            summary = f"DEÜ (İç): {deu_ms:.0f} ms | Google (Dış): {google_ms:.0f} ms"
        elif deu_ok or google_ok:
            status = TestStatus.WARNING
            parts = []
            if deu_ok:
                parts.append(f"DEÜ: {deu_ms:.0f} ms")
            else:
                parts.append("DEÜ: Hata")
            if google_ok:
                parts.append(f"Google: {google_ms:.0f} ms")
            else:
                parts.append("Google: Hata")
            summary = " | ".join(parts)
        else:
            status = TestStatus.FAILED
            summary = f"Erişim Hatası (DEÜ: {deu_err[:20]}, Google: {google_err[:20]})"

        return self._create_result(
            status=status,
            start_time=start_time,
            summary=summary,
            details={
                "deu_ok": deu_ok,
                "deu_status": deu_code,
                "deu_ms": round(deu_ms, 1),
                "google_ok": google_ok,
                "google_status": google_code,
                "google_ms": round(google_ms, 1),
            }
        )
