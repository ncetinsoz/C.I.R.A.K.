"""
AutoTest View: 10-Second Complete L1-L7 Health Report.
Displays 6 test step cards in 3x2 layout with live status and progress updates.
Supports seamless Dark & Light Industrial themes.
"""

import json
from pathlib import Path
import time
from typing import List, Optional
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
from cirak import config
from cirak.backend.autotest import AutoTestRunner
from cirak.core.models import TestResult, TestStatus, AutoTestReport
from cirak.core.worker import BaseWorker
from cirak.gui.theme import ThemeManager


class AutoTestStepCard(QFrame):
    """Card widget for a single test step in AutoTest."""

    def __init__(self, step_num: int, title: str, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("AutoTestStepCard")
        self.step_num = step_num
        self.step_title = title
        self._last_state = "reset"  # "reset", "running", "result"
        self._last_result: Optional[TestResult] = None
        self._init_ui()
        self.reset_card()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        # Header: Step Title and Status Badge
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        self.title_label = QLabel(f"{self.step_num}. {self.step_title}")
        self.title_label.setObjectName("AutoTestStepTitle")
        t_font = QFont("DejaVu Sans", 10, QFont.Bold)
        self.title_label.setFont(t_font)

        self.status_badge = QLabel("BEKLİYOR")
        self.status_badge.setObjectName("AutoTestStepBadge")
        b_font = QFont("DejaVu Sans Mono", 9, QFont.Bold)
        self.status_badge.setFont(b_font)
        self.status_badge.setAlignment(Qt.AlignCenter)
        self.status_badge.setFixedHeight(22)

        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.status_badge)

        # Detail lines
        self.line1 = QLabel("Henüz test edilmedi")
        self.line1.setObjectName("AutoTestStepLine1")
        l1_font = QFont("DejaVu Sans Mono", 10, QFont.Bold)
        self.line1.setFont(l1_font)

        self.line2 = QLabel("")
        self.line2.setObjectName("AutoTestStepLine2")
        l2_font = QFont("DejaVu Sans Mono", 9)
        self.line2.setFont(l2_font)

        layout.addLayout(header_layout)
        layout.addWidget(self.line1)
        layout.addWidget(self.line2)
        layout.addStretch()

    def update_theme(self):
        """Re-apply current card state with active theme palette."""
        if self._last_state == "running":
            self.set_running()
        elif self._last_state == "result" and self._last_result is not None:
            self.set_result(self._last_result)
        else:
            self.reset_card()

    def reset_card(self):
        self._last_state = "reset"
        self._last_result = None
        colors = ThemeManager.get_colors()
        self.title_label.setStyleSheet(
            f"background: transparent; border: none; color: {colors['text_primary']}; font-weight: 700;"
        )
        self.setStyleSheet(f"""
            QFrame#AutoTestStepCard {{
                background-color: {colors['card_bg']};
                border: 1.5px solid {colors['card_border']};
                border-radius: 10px;
            }}
            #AutoTestStepCard QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        self.status_badge.setText("BEKLİYOR")
        self.status_badge.setStyleSheet(f"""
            QLabel#AutoTestStepBadge {{
                background-color: transparent;
                color: {colors['text_muted']};
                border: 1px solid {colors['card_border']};
                border-radius: 4px;
                padding: 1px 6px;
            }}
        """)
        self.line1.setText("Henüz test edilmedi")
        self.line1.setStyleSheet(f"background: transparent; border: none; color: {colors['text_secondary']};")
        self.line2.setText("")
        self.line2.setStyleSheet(f"background: transparent; border: none; color: {colors['text_muted']};")

    def set_running(self):
        self._last_state = "running"
        colors = ThemeManager.get_colors()
        accent = colors["accent_cyan"]
        self.title_label.setStyleSheet(
            f"background: transparent; border: none; color: {colors['text_primary']}; font-weight: 700;"
        )
        self.setStyleSheet(f"""
            QFrame#AutoTestStepCard {{
                background-color: {colors['card_bg']};
                border: 1.5px solid {accent};
                border-radius: 10px;
            }}
            #AutoTestStepCard QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        self.status_badge.setText("TEST EDİLİYOR...")
        self.status_badge.setStyleSheet(f"""
            QLabel#AutoTestStepBadge {{
                background-color: rgba(6, 182, 212, 0.15);
                color: {accent};
                border: 1px solid {accent};
                border-radius: 4px;
                padding: 1px 6px;
            }}
        """)
        self.line1.setText("Paketler gönderiliyor...")
        self.line1.setStyleSheet(f"background: transparent; border: none; color: {accent};")

    def set_result(self, result: TestResult):
        self._last_state = "result"
        self._last_result = result
        is_dark = ThemeManager.get_current_theme() == config.THEME_DARK
        colors = ThemeManager.get_colors()
        self.title_label.setStyleSheet(
            f"background: transparent; border: none; color: {colors['text_primary']}; font-weight: 700;"
        )

        if result.status == TestStatus.PASSED:
            badge_text = f"✓ {result.duration_ms:.0f} ms" if (result.duration_ms > 0 and self.step_num in (3, 4, 5, 6)) else "✓ PASS"
            border_color = colors["status_success"]
            badge_bg = "#022c22" if is_dark else "#dcfce7"
            badge_style = f"""
                QLabel#AutoTestStepBadge {{
                    background-color: {badge_bg};
                    color: {border_color};
                    border: 1px solid {border_color};
                    border-radius: 4px;
                    padding: 1px 6px;
                }}
            """
            line1_color = colors["text_primary"]
            line2_color = border_color
        elif result.status == TestStatus.WARNING:
            badge_text = "! UYARI"
            border_color = colors["status_warning"]
            badge_bg = "#451a03" if is_dark else "#fef3c7"
            badge_style = f"""
                QLabel#AutoTestStepBadge {{
                    background-color: {badge_bg};
                    color: {border_color};
                    border: 1px solid {border_color};
                    border-radius: 4px;
                    padding: 1px 6px;
                }}
            """
            line1_color = colors["text_primary"]
            line2_color = border_color
        elif result.status == TestStatus.FAILED:
            badge_text = "✗ FAIL"
            border_color = colors["status_error"]
            badge_bg = "#450a0a" if is_dark else "#fee2e2"
            badge_style = f"""
                QLabel#AutoTestStepBadge {{
                    background-color: {badge_bg};
                    color: {border_color};
                    border: 1px solid {border_color};
                    border-radius: 4px;
                    padding: 1px 6px;
                }}
            """
            line1_color = border_color
            line2_color = colors["text_secondary"]
        else:
            badge_text = "ATLANDI"
            border_color = colors["card_border"]
            badge_style = f"""
                QLabel#AutoTestStepBadge {{
                    background-color: transparent;
                    color: {colors['text_muted']};
                    border: 1px solid {border_color};
                    border-radius: 4px;
                    padding: 1px 6px;
                }}
            """
            line1_color = colors["text_muted"]
            line2_color = colors["text_secondary"]

        self.setStyleSheet(f"""
            QFrame#AutoTestStepCard {{
                background-color: {colors['card_bg']};
                border: 1.5px solid {border_color};
                border-radius: 10px;
            }}
            #AutoTestStepCard QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        self.status_badge.setText(badge_text)
        self.status_badge.setStyleSheet(badge_style)

        summary_parts = result.summary.split("|")
        self.line1.setText(summary_parts[0].strip() if summary_parts else result.summary)
        self.line1.setStyleSheet(f"background: transparent; color: {line1_color};")

        if len(summary_parts) > 1:
            self.line2.setText(" | ".join(p.strip() for p in summary_parts[1:]))
            self.line2.setStyleSheet(f"background: transparent; color: {line2_color};")
        else:
            self.line2.setText(f"Süre: {result.duration_ms:.1f} ms" if result.duration_ms > 0 else "")
            self.line2.setStyleSheet(f"background: transparent; color: {line2_color};")


class AutoTestView(QWidget):
    """AutoTest main view container."""

    back_requested = Signal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.runner: Optional[AutoTestRunner] = None
        self.last_report: Optional[AutoTestReport] = None
        self._init_ui()
        self.update_theme()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 8, 12, 8)
        main_layout.setSpacing(8)

        # 1. Header Toolbar
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)

        self.back_btn = QPushButton("← Geri")
        self.back_btn.setFixedSize(70, 30)
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.clicked.connect(self.back_requested.emit)

        self.title_lbl = QLabel("AutoTest (10 Saniyede Tam Sağlık Raporu)")
        title_font = QFont("DejaVu Sans", 11, QFont.Bold)
        self.title_lbl.setFont(title_font)

        self.summary_badge = QLabel("HAZIR")
        badge_font = QFont("DejaVu Sans Mono", 9, QFont.Bold)
        self.summary_badge.setFont(badge_font)

        self.retest_btn = QPushButton("Yeniden Test Et")
        self.retest_btn.setProperty("class", "PrimaryBtn")
        self.retest_btn.setFixedHeight(30)
        self.retest_btn.setCursor(Qt.PointingHandCursor)
        self.retest_btn.clicked.connect(self.start_autotest)

        header.addWidget(self.back_btn)
        header.addWidget(self.title_lbl)
        header.addStretch()
        header.addWidget(self.summary_badge)
        header.addWidget(self.retest_btn)

        # 2. Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setValue(0)

        # 3. 3x2 Grid of Test Cards
        cards_grid = QGridLayout()
        cards_grid.setSpacing(10)
        cards_grid.setContentsMargins(0, 0, 0, 0)

        self.card_l1 = AutoTestStepCard(1, "Fiziksel Link")
        self.card_l2 = AutoTestStepCard(2, "Switch & Port (CDP/LLDP)")
        self.card_l3 = AutoTestStepCard(3, "DHCP Sunucusu")
        self.card_l4 = AutoTestStepCard(4, "Gateway Ping")
        self.card_l5 = AutoTestStepCard(5, "DNS Çözümleme")
        self.card_l6 = AutoTestStepCard(6, "Erişim Testi")

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

        # 4. Bottom Footer Bar (Report Summary & Save)
        self.footer = QFrame()
        self.footer.setFixedHeight(36)
        f_layout = QHBoxLayout(self.footer)
        f_layout.setContentsMargins(12, 0, 12, 0)

        self.footer_text = QLabel("Tüm L1-L7 katmanlarını gerçek ağ donanımı üzerinden test eder.")
        f_font = QFont("DejaVu Sans Mono", 9)
        self.footer_text.setFont(f_font)

        self.save_btn = QPushButton("📄 Raporu Kaydet (JSON)")
        self.save_btn.setFixedHeight(24)
        self.save_btn.clicked.connect(self._save_report)

        f_layout.addWidget(self.footer_text)
        f_layout.addStretch()
        f_layout.addWidget(self.save_btn)

        main_layout.addLayout(header)
        main_layout.addWidget(self.progress_bar)
        main_layout.addLayout(cards_grid)
        main_layout.addWidget(self.footer)

    def update_theme(self):
        """Update AutoTestView and all 6 step cards for Dark and Light mode."""
        colors = ThemeManager.get_colors()
        self.title_lbl.setStyleSheet(f"background: transparent; color: {colors['accent_cyan']}; font-weight: 800;")
        self.footer.setStyleSheet(f"""
            QFrame {{
                background-color: {colors['card_bg']};
                border: 1px solid {colors['card_border']};
                border-radius: 8px;
            }}
        """)
        self.footer_text.setStyleSheet(f"background: transparent; color: {colors['text_secondary']};")
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {colors['accent_cyan']};
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 700;
            }}
        """)
        if not self.last_report:
            self.summary_badge.setStyleSheet(f"""
                background-color: transparent;
                color: {colors['text_secondary']};
                border: 1px solid {colors['card_border']};
                border-radius: 4px;
                padding: 3px 10px;
            """)
        for c in self.cards:
            c.update_theme()

    def start_autotest(self):
        """Execute real network diagnostic suite on background thread safely via Qt Signals."""
        colors = ThemeManager.get_colors()
        self.retest_btn.setEnabled(False)
        self.summary_badge.setText("TEST BAŞLATILDI...")
        self.summary_badge.setStyleSheet(f"""
            background-color: rgba(6, 182, 212, 0.15);
            color: {colors['accent_cyan']};
            border: 1px solid {colors['accent_cyan']};
            border-radius: 4px;
            padding: 3px 10px;
        """)
        self.progress_bar.setValue(0)

        for c in self.cards:
            c.reset_card()

        def _execute_suite():
            self.runner = AutoTestRunner(
                simulate=False,
                on_step_start=lambda idx, name: self._active_worker.signals.step_started.emit(idx, name),
                on_step_done=lambda idx, res: self._active_worker.signals.step_done.emit(idx, res),
            )
            return self.runner.run_all()

        self._active_worker = BaseWorker(_execute_suite)
        self._active_worker.signals.step_started.connect(self._on_step_started, Qt.QueuedConnection)
        self._active_worker.signals.step_done.connect(self._on_step_completed, Qt.QueuedConnection)
        self._active_worker.signals.result.connect(self._on_autotest_finished, Qt.QueuedConnection)
        self._active_worker.signals.error.connect(self._on_autotest_error, Qt.QueuedConnection)
        QThreadPool.globalInstance().start(self._active_worker)

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
        self.last_report = report
        self.retest_btn.setEnabled(True)
        self.progress_bar.setValue(100)
        is_dark = ThemeManager.get_current_theme() == config.THEME_DARK
        colors = ThemeManager.get_colors()

        sec = report.total_duration_ms / 1000.0
        self.footer_text.setText(f"Süre: {sec:.1f} saniye • {report.passed_count}/6 test başarıyla tamamlandı.")

        if report.overall_passed:
            self.summary_badge.setText(f"✓ TÜM TESTLER GEÇTİ ({report.passed_count}/6)")
            bg = "#022c22" if is_dark else "#dcfce7"
            fg = colors["status_success"]
        else:
            self.summary_badge.setText(f"! TEST TAMAMLANDI ({report.passed_count}/6)")
            bg = "#451a03" if is_dark else "#fef3c7"
            fg = colors["status_warning"]

        self.summary_badge.setStyleSheet(f"""
            background-color: {bg};
            color: {fg};
            border: 1px solid {fg};
            border-radius: 4px;
            padding: 3px 10px;
        """)

    def _on_autotest_error(self, err_tuple):
        self.retest_btn.setEnabled(True)
        self.summary_badge.setText("HATA OLUŞTU")

    def _save_report(self):
        if not self.last_report:
            return
        report_data = {
            "timestamp": time.time(),
            "overall_passed": self.last_report.overall_passed,
            "duration_ms": self.last_report.total_duration_ms,
            "steps": [s.__dict__ for s in self.last_report.steps],
        }
        out_file = Path("/tmp/cirak_autotest_report.json")
        out_file.write_text(json.dumps(report_data, indent=2, ensure_ascii=False))
        self.save_btn.setText("✓ Kaydedildi!")
