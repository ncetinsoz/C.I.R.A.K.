"""
Tests for AutoTest 6-step L1-L7 orchestrator.
"""

from cirak.backend.autotest import AutoTestRunner
from cirak.core.models import TestStatus


def test_autotest_full_chain_simulation():
    started_steps = []
    completed_steps = []

    def on_start(idx, name):
        started_steps.append((idx, name))

    def on_done(idx, res):
        completed_steps.append((idx, res))

    runner = AutoTestRunner(
        interface="eth0",
        simulate=True,
        on_step_start=on_start,
        on_step_done=on_done,
    )
    report = runner.run_all()

    assert report.overall_passed is True
    assert report.total_steps_count == 6
    assert report.completed_steps_count == 6
    assert report.passed_count == 6
    assert len(started_steps) == 6
    assert len(completed_steps) == 6
    assert report.total_duration_ms > 0

    step_names = [s.name for s in report.steps]
    assert "1. Fiziksel Link" in step_names[0]
    assert "2. Switch & Port (LLDP)" in step_names[1]
    assert "3. DHCP Sunucusu" in step_names[2]
    assert "4. Gateway Ping" in step_names[3]
    assert "5. DNS Çözümleme" in step_names[4]
    assert "6. Dış Ağ (ULAKBIM)" in step_names[5]
