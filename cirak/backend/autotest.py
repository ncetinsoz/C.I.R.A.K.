"""
AutoTest Orchestrator: Layer 1 to Layer 7 complete health validation chain.
Executes the 6 core tests in sequence within ~5-10 seconds:
1. Physical Link (L1)
2. Switch & Port LLDP/CDP (L2)
3. DHCP Server & Lease (L3)
4. Gateway Ping & ARP (L3)
5. DNS Resolution (L7)
6. External Network / Web Connectivity (L7)
"""

import time
from typing import Callable, Optional, List
from cirak.backend.base import BaseTest
from cirak.backend.network_detector import NetworkDetector
from cirak.backend.physical_link import PhysicalLinkTest
from cirak.backend.lldp_cdp import LLDPCdpTest
from cirak.backend.dhcp import DHCPTest
from cirak.backend.ping import PingTest
from cirak.backend.dns_test import DNSTest
from cirak.backend.external_test import ExternalTest
from cirak.core.models import TestResult, TestStatus, AutoTestReport


class AutoTestRunner:
    """Coordinates and runs the 6-stage L1-L7 AutoTest suite with real hardware telemetry."""

    def __init__(
        self,
        interface: Optional[str] = None,
        simulate: bool = False,
        on_step_start: Optional[Callable[[int, str], None]] = None,
        on_step_done: Optional[Callable[[int, TestResult], None]] = None,
    ):
        self.interface = interface or NetworkDetector.get_active_interface()
        self.simulate = simulate
        self.on_step_start = on_step_start
        self.on_step_done = on_step_done
        self._is_cancelled = False
        self._current_test: Optional[BaseTest] = None

    def cancel(self):
        """Cancel running suite."""
        self._is_cancelled = True
        if self._current_test:
            self._current_test.cancel()

    def run_all(self) -> AutoTestReport:
        """Run all 6 test steps in sequence."""
        self._is_cancelled = False
        start_suite = time.time()

        steps_classes = [
            PhysicalLinkTest(interface=self.interface, simulate=self.simulate),
            LLDPCdpTest(interface=self.interface, simulate=self.simulate),
            DHCPTest(interface=self.interface, simulate=self.simulate),
            PingTest(interface=self.interface, simulate=self.simulate),
            DNSTest(interface=self.interface, simulate=self.simulate),
            ExternalTest(interface=self.interface, simulate=self.simulate),
        ]

        results: List[TestResult] = []

        for idx, test_instance in enumerate(steps_classes):
            if self._is_cancelled:
                break

            self._current_test = test_instance
            if self.on_step_start:
                try:
                    self.on_step_start(idx, test_instance.name)
                except Exception:
                    pass

            result = test_instance.run()
            results.append(result)

            if self.on_step_done:
                try:
                    self.on_step_done(idx, result)
                except Exception:
                    pass

            # If L1 physically failed (no cable), skip the remaining tests
            if idx == 0 and result.status == TestStatus.FAILED and not self.simulate:
                for rem_idx in range(idx + 1, len(steps_classes)):
                    rem_test = steps_classes[rem_idx]
                    skipped_res = TestResult(
                        name=rem_test.name,
                        status=TestStatus.SKIPPED,
                        summary="Fiziksel bağlantı olmadığı için atlandı",
                        timestamp=time.time()
                    )
                    results.append(skipped_res)
                    if self.on_step_done:
                        self.on_step_done(rem_idx, skipped_res)
                break

        total_duration = (time.time() - start_suite) * 1000.0
        overall_passed = all(r.status in (TestStatus.PASSED, TestStatus.WARNING) for r in results) and len(results) == 6

        return AutoTestReport(
            overall_passed=overall_passed,
            total_duration_ms=round(total_duration, 2),
            steps=results,
            completed_steps_count=len(results),
            total_steps_count=6,
        )
