"""
Throughput & Latency Speed Test Engine for Ç.I.R.A.K.
Measures real dual-stream network performance:
  1. Internal Network (DEÜ Campus / www.deu.edu.tr)
  2. External Network (Global CDN / Cloudflare / Google)
"""

from dataclasses import dataclass
import re
import socket
import subprocess
import time
import urllib.request
import urllib.error
from typing import Optional, Callable
from cirak import config
from cirak.backend.network_detector import NetworkDetector


@dataclass
class SpeedTargetResult:
    target_name: str
    target_url: str
    host: str
    download_mbps: float = 0.0
    latency_ms: float = 0.0
    jitter_ms: float = 0.0
    packet_loss_pct: float = 0.0
    http_status: int = 0
    status_desc: str = "Bekliyor"


@dataclass
class DualSpeedTestReport:
    internal: SpeedTargetResult
    external: SpeedTargetResult
    total_duration_ms: float = 0.0


class SpeedTestEngine:
    """Executes real bandwidth throughput and latency diagnostics."""

    def __init__(
        self,
        internal_url: str = "http://www.deu.edu.tr",
        external_url: str = "https://speed.cloudflare.com/__down?bytes=5000000",
        external_fallback_url: str = "http://www.google.com",
        interface: Optional[str] = None,
        simulate: bool = False,
    ):
        self.internal_url = internal_url
        self.external_url = external_url
        self.external_fallback_url = external_fallback_url
        self.interface = interface or NetworkDetector.get_active_interface()
        self.simulate = simulate
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run_test(
        self,
        on_progress: Optional[Callable[[str, int], None]] = None
    ) -> DualSpeedTestReport:
        """Run sequential dual-stream test: internal campus first, then external internet."""
        self._is_cancelled = False
        t_start = time.perf_counter()

        if self.simulate:
            time.sleep(0.4)
            internal = SpeedTargetResult(
                target_name="İç Ağ (DEÜ Kampüs)",
                target_url=self.internal_url,
                host="www.deu.edu.tr",
                download_mbps=94.5,
                latency_ms=2.1,
                jitter_ms=0.4,
                packet_loss_pct=0.0,
                http_status=200,
                status_desc="Mükemmel (Kampüs İçi Hızlı Erişim)",
            )
            external = SpeedTargetResult(
                target_name="Dış Ağ (İnternet / CDN)",
                target_url=self.external_url,
                host="speed.cloudflare.com",
                download_mbps=68.2,
                latency_ms=14.8,
                jitter_ms=1.1,
                packet_loss_pct=0.0,
                http_status=200,
                status_desc="Yüksek Hız (Stabil İnternet)",
            )
            return DualSpeedTestReport(
                internal=internal,
                external=external,
                total_duration_ms=(time.perf_counter() - t_start) * 1000.0,
            )

        # 1. Internal Campus Test (DEÜ)
        if on_progress:
            on_progress("İç Ağ (DEÜ) test ediliyor...", 25)
        internal = self._measure_target(
            name="İç Ağ (DEÜ Kampüs)",
            url=self.internal_url,
            default_host="www.deu.edu.tr",
            chunk_size=1024 * 128,
            max_duration_sec=3.0,
        )

        if self._is_cancelled:
            return DualSpeedTestReport(internal=internal, external=SpeedTargetResult("Dış Ağ", self.external_url, "none"))

        # 2. External CDN / Internet Test
        if on_progress:
            on_progress("Dış Ağ (İnternet) test ediliyor...", 65)
        external = self._measure_target(
            name="Dış Ağ (İnternet / CDN)",
            url=self.external_url,
            default_host="speed.cloudflare.com",
            chunk_size=1024 * 256,
            max_duration_sec=4.0,
            fallback_url=self.external_fallback_url,
        )

        if on_progress:
            on_progress("Tamamlandı", 100)

        total_ms = (time.perf_counter() - t_start) * 1000.0
        return DualSpeedTestReport(internal=internal, external=external, total_duration_ms=total_ms)

    def _measure_target(
        self,
        name: str,
        url: str,
        default_host: str,
        chunk_size: int,
        max_duration_sec: float,
        fallback_url: Optional[str] = None,
    ) -> SpeedTargetResult:
        host = default_host
        try:
            parsed_host = url.split("//")[-1].split("/")[0]
            if parsed_host:
                host = parsed_host
        except Exception:
            pass

        # 1. ICMP ping latency & jitter
        latency, jitter, loss = self._ping_host(host)

        # 2. HTTP throughput download stream
        mbps, status_code = self._download_throughput(url, chunk_size, max_duration_sec)

        # Fallback if primary CDN endpoint failed (e.g. firewalled)
        if mbps == 0.0 and fallback_url:
            mbps, status_code = self._download_throughput(fallback_url, chunk_size, max_duration_sec)

        # Rate quality
        if mbps >= 80.0:
            quality = "Mükemmel (Yüksek Hız)"
        elif mbps >= 30.0:
            quality = "İyi (Stabil Erişim)"
        elif mbps > 0.0:
            quality = "Orta / Yavaş"
        elif status_code in (200, 301, 302):
            quality = "HTTP Erişilebilir"
        else:
            quality = "Erişim Hatası"

        return SpeedTargetResult(
            target_name=name,
            target_url=url,
            host=host,
            download_mbps=round(mbps, 1),
            latency_ms=round(latency, 1),
            jitter_ms=round(jitter, 1),
            packet_loss_pct=round(loss, 1),
            http_status=status_code,
            status_desc=quality,
        )

    def _ping_host(self, host: str) -> tuple[float, float, float]:
        """Ping host 3 times and return (avg_rtt, jitter, loss_pct)."""
        cmd = ["ping"]
        if self.interface and self.interface != "lo":
            cmd += ["-I", self.interface]
        cmd += ["-c", "3", "-W", "1", host]

        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=3.5)
            output = res.stdout

            loss_match = re.search(r"(\d+(?:\.\d+)?)%\s*packet loss", output)
            loss_pct = float(loss_match.group(1)) if loss_match else 100.0

            rtt_match = re.search(r"rtt min/avg/max/mdev = [\d\.]+/([\d\.]+)/[\d\.]+/([\d\.]+)", output)
            if rtt_match:
                avg_rtt = float(rtt_match.group(1))
                jitter = float(rtt_match.group(2))
                return avg_rtt, jitter, loss_pct
        except Exception:
            pass
        return 0.0, 0.0, 100.0

    def _download_throughput(self, url: str, chunk_size: int, max_duration_sec: float) -> tuple[float, int]:
        """Stream data chunks from HTTP endpoint and calculate real megabits/sec."""
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "CIRAK-SpeedTest/1.0",
                "Accept-Encoding": "identity",
            }
        )

        total_bytes = 0
        status_code = 0
        try:
            t_start = time.perf_counter()
            with urllib.request.urlopen(req, timeout=max_duration_sec + 1.0) as resp:
                status_code = resp.getcode()
                while True:
                    if self._is_cancelled:
                        break
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    elapsed = time.perf_counter() - t_start
                    if elapsed >= max_duration_sec:
                        break

            elapsed = max(time.perf_counter() - t_start, 0.05)
            # Megabits per second = (bytes * 8) / (seconds * 1,000,000)
            mbps = (total_bytes * 8.0) / (elapsed * 1_000_000.0)
            return mbps, status_code
        except Exception:
            return 0.0, status_code
