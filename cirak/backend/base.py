"""
Base class for network diagnostic tests.
"""

from abc import ABC, abstractmethod
import time
from typing import Optional
from cirak.core.models import TestResult, TestStatus


class BaseTest(ABC):
    """Abstract base class for all Ç.I.R.A.K. backend diagnostic tests."""
    __test__ = False

    def __init__(self, name: str, interface: str = "eth0", simulate: bool = False):
        self.name = name
        self.interface = interface
        self.simulate = simulate
        self._is_cancelled = False

    def cancel(self):
        """Request test cancellation."""
        self._is_cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self._is_cancelled

    @abstractmethod
    def run(self) -> TestResult:
        """Execute the test and return a TestResult."""
        pass

    def _create_result(
        self,
        status: TestStatus,
        start_time: float,
        summary: str,
        details: Optional[dict] = None
    ) -> TestResult:
        """Helper to create standardized TestResult."""
        duration = (time.time() - start_time) * 1000.0
        return TestResult(
            name=self.name,
            status=status,
            duration_ms=round(duration, 2),
            summary=summary,
            details=details or {},
            timestamp=time.time(),
        )
