"""
AutoTest View: 10-Second Complete L1-L7 Health Report.
Displays 6 test step cards in 2x3 layout with live status and progress updates.
"""

from typing import List
from PySide6.QtCore import Qt, Signal, QThreadPool
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QFrame,
    QProgressBar,
)
from cirak.backend.autotest import AutoTestRunner
from cirak.core.models import TestResult, TestStatus, AutoTestReport
from cirak.core.worker import BaseWorker


class AutoTestStepCard(QFrame):
    """Card widget for a single test step in AutoTest."""

    def __init__(self, step_num: int, title: str, parent: QWidget = None):
        super().__init__(parent)
        self.step_num = step_num
        self.step_title = title
        self.setProperty("class", "StatusCard")
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # Header: Step Title and Status Badge
        header_layout = QHBoxLayout()
        self.title_label = QLabel(f"{self.step_num}. {self.step_title}")
        self.title_label.setStyleSheet("font-weight: 800; font-size: 11px;")

        self.status_badge = QLabel("BEKLİYOR")
        self.status_badge.setStyleSheet(
            "font-size: 10px; font-weight: bold; color: #94a3b8; "
            "border: 1px solid #334155; border-radius: 4px; padding: 1px 4px;"
        )

        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.status_badge)

        # Detail lines
        self.line1 = QLabel("Henüz test edilmedi")
        self.line1.setStyleSheet("color: #94a3b8; font-size: 10px; font-family: monospace;")
        self.line2 = QLabel("")
        self.line2.setStyleSheet("color: #94a3b8; font-size: 10px; font-family: monospace;")

        layout.addLayout(header_layout)
        layout.addWidget(self.line1)
        layout.addWidget(self.line2)
        layout.addStretch()

    def set_running(self):
        self.status_badge.setText("TEST EDİLİYOR...")
        self.status_badge.setStyleSheet(
            "font-size: 10px; font-weight: bold; color: #22d3ee; "
            "border: 1px solid #22d3ee; border-radius: 4px; padding: 1px 4px;"
        )

    def set_result(self, result: TestResult):
        if result.status == TestStatus.PASSED:
            self.status_badge.setText("✓ PASS")
            self.status_badge.setStyleSheet(
                "font-size: 10px; font-weight: bold; color: #10b981; "
                "background-color: #022c22; border: 1px solid #10b981; border-radius: 4px; padding: 1px 4px;"
            )
        elif result.status == TestStatus.WARNING:
            self.status_badge.setText("! UYARI")
            self.status_badge.setStyleSheet(
                "font-size: 10px; font-weight: bold; color: #f59e0b; "
                "background-color: #451a03; border: 1px solid #f59e0b; border-radius: 4px; padding: 1px 4px;"
            )
        elif result.status == TestStatus.FAILED:
            self.status_badge.setText("✗ FAIL")
            self.status_badge.setStyleSheet(
                "font-size: 10px; font-weight: bold; color: #ef4444; "
                "background-color: #450a0a; border: 1px solid #ef4444; border-radius: 4px; padding: 1px 4px;"
            )
        else:
            self.status_badge.setText("ATLANDI")
            self.status_badge.setStyleSheet(
                "font-size: 10px; font-weight: bold; color: #64748b; "
                "border: 1px solid #475569; border-radius: 4px; padding: 1px 4px;"
            )

        self.line1.setText(result.summary)
        if result.duration_ms > 0:
            self.line2.setText(f"Süre: {result.duration_ms:.1f} ms")


class AutoTestView(QWidget):
    """AutoTest main view container."""

    back_requested = Signal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.runner: AutoTestRunner = None
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 10, 14, 10)
        main_layout.setSpacing(8)

        # 1. Header Toolbar
        header = QHBoxLayout()
        self.back_btn = QPushButton("← Geri")
        self.back_btn.setFixedSize(70, 30)
        self.back_btn.clicked.connect(self.back_requested.emit)

        title = QLabel("AutoTest (10 Saniyede Tam Sağlık Raporu)")
        title.setStyleSheet("font-size: 13px; font-weight: 800; color: #22d3ee;")

        self.summary_badge = QLabel("HAZIR")
        self.summary_badge.setStyleSheet(
            "font-size: 11px; font-weight: bold; color: #94a3b8; "
            "border: 1px solid #334155; border-radius: 4px; padding: 2px 8px;"
        )

        self.retest_btn = QPushButton("Yeniden Test Et")
        self.retest_btn.setProperty("class", "PrimaryBtn")
        self.retest_btn.setFixedHeight(30)
        self.retest_btn.clicked.connect(self.start_autotest)

        header.addWidget(self.back_btn)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.summary_badge)
        header.addWidget(self.retest_btn)

        # 2. Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(5)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setValue(0)

        # 3. 2x3 Grid of Test Cards
        cards_grid = QGridLayout()
        cards_grid.setSpacing(8)

        self.card_l1 = AutoTestStepCard(1, "Fiziksel Link")
        self.card_l2 = AutoTestStepCard(2, "Switch & Port (LLDP)")
        self.card_l3 = AutoTestStepCard(3, "DHCP Sunucusu")
        self.card_l4 = AutoTestStepCard(4, "Gateway Ping")
        self.card_l5 = AutoTestStepCard(5, "DNS Çözümleme")
        self.card_l6 = AutoTestStepCard(6, "Dış Ağ (ULAKBIM)")

        self.cards: List[AutoTestStepCard] = [
            self.card_l1, self.card_l2, self.card_l3,
            self.card_l4, self.card_l5, self.card_l6,
        ]

        cards_grid.addWidget(self.card_l1, 0, 0)
        cards_grid.addWidget(self.card_l2, 0, 1)
        cards_grid.addWidget(self.card_l3, 0, 2)
        cards_grid.addWidget(self.card_l4, 1, 0)
        cards_grid.addWidget(self.card_l5, 1, 1)
        cards_grid.addWidget(self.card_l6, 1, 2)

        main_layout.addLayout(header)
        main_layout.addWidget(self.progress_bar)
        main_layout.addLayout(cards_grid)

    def start_autotest(self):
        """Run AutoTest via QThreadPool."""
        self.retest_btn.setEnabled(False)
        self.summary_badge.setText("TEST BAŞLATILDI...")
        self.summary_badge.setStyleSheet(
            "font-size: 11px; font-weight: bold; color: #22d3ee; "
            "border: 1px solid #22d3ee; border-radius: 4px; padding: 2px 8px;"
        )
        self.progress_bar.setValue(0)

        self.runner = AutoTestRunner(
            simulate=True,  # Default simulate for safety in headless/lab environments
            on_step_start=self._on_step_started,
            on_step_done=self._on_step_completed,
        )

        worker = BaseWorker(self.runner.run_all)
        worker.signals.result.connect(self._on_autotest_finished)
        worker.signals.error.connect(self._on_autotest_error)
        QThreadPool.globalInstance().start(worker)

    def _on_step_started(self, idx: int, name: str):
        if 0 <= idx < len(self.cards):
            self.cards[idx].set_running()
            pct = int((idx / 6.0) * 100)
            self.progress_bar.setValue(pct)

    def _on_step_completed(self, idx: int, result: TestResult):
        if 0 <= idx < len(self.cards):
            self.cards[idx].set_result(result)
            pct = int(((idx + 1) / 6.0) * 100)
            self.progress_bar.setValue(pct)

    def _on_autotest_finished(self, report: AutoTestReport):
        self.retest_btn.setEnabled(True)
        self.progress_bar.setValue(100)

        if report.overall_passed:
            self.summary_badge.setText(f"✓ TÜM TESTLER GEÇTİ ({report.passed_count}/6)")
            self.summary_badge.setStyleSheet(
                "font-size: 11px; font-weight: bold; color: #10b981; "
                "background-color: #022c22; border: 1px solid #10b981; border-radius: 4px; padding: 2px 8px;"
            )
        else:
            self.summary_badge.setText(f"✗ BAŞARISIZ ({report.passed_count}/6)")
            self.summary_badge.setStyleSheet(
                "font-size: 11px; font-weight: bold; color: #ef4444; "
                "background-color: #450a0a; border: 1px solid #ef4444; border-radius: 4px; padding: 2px 8px;"
            )

    def _on_autotest_error(self, err_tuple):
        self.retest_btn.setEnabled(True)
        self.summary_badge.setText("HATA OLUŞTU")
