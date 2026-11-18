"""
Dual-Stream Speed Test View for Ç.I.R.A.K.
Side-by-side comparison of:
  - Internal Network (DEÜ Campus LAN Hat Kapasitesi / www.deu.edu.tr / iperf3)
  - External Network (Global Internet CDN / Cloudflare)
Supports seamless Dark and Light Industrial themes.
"""

from typing import Optional
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
from cirak.backend.speed_test import SpeedTestEngine, DualSpeedTestReport, SpeedTargetResult
from cirak.core.worker import BaseWorker
from cirak.gui.theme import ThemeManager


class SpeedColumnCard(QFrame):
    """Side card displaying speed metrics for internal or external target."""

    def __init__(self, title: str, subtitle: str, accent_color: str, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("SpeedColumnCard")
        self.accent_color = accent_color
        self.title_text = title
        self.subtitle_text = subtitle
        self._last_state = "reset"
        self._last_res: Optional[SpeedTargetResult] = None
        self._init_ui()
        self.reset_card()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # Header: Title + Target Subtitle
        header_box = QVBoxLayout()
        header_box.setSpacing(2)

        self.title_label = QLabel(self.title_text)
        t_font = QFont("DejaVu Sans", 11, QFont.Bold)
        self.title_label.setFont(t_font)

        self.sub_label = QLabel(self.subtitle_text)
        s_font = QFont("DejaVu Sans Mono", 9)
        self.sub_label.setFont(s_font)

        header_box.addWidget(self.title_label)
        header_box.addWidget(self.sub_label)
        layout.addLayout(header_box)

        # Large Digital Speed Value
        self.speed_val_label = QLabel("-- Mbps")
        val_font = QFont("DejaVu Sans Mono", 24, QFont.Bold)
        self.speed_val_label.setFont(val_font)
        self.speed_val_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.speed_val_label)

        # Status badge below speed
        self.quality_badge = QLabel("BEKLİYOR")
        b_font = QFont("DejaVu Sans Mono", 9, QFont.Bold)
        self.quality_badge.setFont(b_font)
        self.quality_badge.setAlignment(Qt.AlignCenter)
        self.quality_badge.setFixedHeight(22)
        layout.addWidget(self.quality_badge)

        # Divider
        self.divider = QFrame()
        self.divider.setFrameShape(QFrame.HLine)
        layout.addWidget(self.divider)

        # Metrics Details Grid (2 columns x 2 rows)
        grid = QGridLayout()
        grid.setSpacing(6)
        grid.setContentsMargins(0, 4, 0, 4)

        self.lbl_rtt_t = QLabel("Gecikme (RTT):")
        self.lbl_rtt_v = QLabel("-- ms")

        self.lbl_jit_t = QLabel("Jitter:")
        self.lbl_jit_v = QLabel("-- ms")

        self.lbl_loss_t = QLabel("Paket Kaybı:")
        self.lbl_loss_v = QLabel("-- %")

        self.lbl_http_t = QLabel("HTTP Yanıt:")
        self.lbl_http_v = QLabel("--")

        self._title_labels = [self.lbl_rtt_t, self.lbl_jit_t, self.lbl_loss_t, self.lbl_http_t]
        self._val_labels = [self.lbl_rtt_v, self.lbl_jit_v, self.lbl_loss_v, self.lbl_http_v]

        grid.addWidget(self.lbl_rtt_t, 0, 0)
        grid.addWidget(self.lbl_rtt_v, 0, 1)
        grid.addWidget(self.lbl_jit_t, 0, 2)
        grid.addWidget(self.lbl_jit_v, 0, 3)

        grid.addWidget(self.lbl_loss_t, 1, 0)
        grid.addWidget(self.lbl_loss_v, 1, 1)
        grid.addWidget(self.lbl_http_t, 1, 2)
        grid.addWidget(self.lbl_http_v, 1, 3)

        layout.addLayout(grid)
        layout.addStretch()

    def _apply_common_theme(self):
        colors = ThemeManager.get_colors()
        self.title_label.setStyleSheet(
            f"background: transparent; border: none; color: {self.accent_color}; font-weight: 800;"
        )
        self.sub_label.setStyleSheet(
            f"background: transparent; border: none; color: {colors['text_secondary']};"
        )
        self.divider.setStyleSheet(f"background-color: {colors['card_border']}; max-height: 1px;")
        for tl in self._title_labels:
            tl.setStyleSheet(f"background: transparent; border: none; color: {colors['text_muted']}; font-size: 11px;")
        for vl in self._val_labels:
            vl.setStyleSheet(
                f"background: transparent; border: none; color: {colors['text_primary']}; font-family: monospace; font-weight: bold; font-size: 11px;"
            )
        self.setStyleSheet(f"""
            QFrame#SpeedColumnCard {{
                background-color: {colors['card_bg']};
                border: 1.5px solid {self.accent_color};
                border-radius: 12px;
            }}
            #SpeedColumnCard QLabel {{
                background: transparent;
                border: none;
            }}
        """)

    def update_theme(self):
        if self._last_state == "running":
            self.set_running()
        elif self._last_state == "result" and self._last_res is not None:
            self.update_result(self._last_res)
        else:
            self.reset_card()

    def reset_card(self):
        self._last_state = "reset"
        self._last_res = None
        colors = ThemeManager.get_colors()
        self._apply_common_theme()
        self.speed_val_label.setText("-- Mbps")
        self.speed_val_label.setStyleSheet(
            f"background: transparent; border: none; color: {colors['text_muted']}; font-weight: 900;"
        )
        self.quality_badge.setText("BEKLİYOR")
        self.quality_badge.setStyleSheet(f"""
            background-color: transparent;
            color: {colors['text_muted']};
            border: 1px solid {colors['card_border']};
            border-radius: 4px;
            padding: 2px 6px;
        """)
        self.lbl_rtt_v.setText("-- ms")
        self.lbl_jit_v.setText("-- ms")
        self.lbl_loss_v.setText("-- %")
        self.lbl_http_v.setText("--")

    def set_running(self):
        self._last_state = "running"
        self._apply_common_theme()
        self.speed_val_label.setText("ÖLÇÜLÜYOR...")
        self.speed_val_label.setStyleSheet(
            f"background: transparent; border: none; color: {self.accent_color}; font-weight: 800; font-size: 18px;"
        )
        self.quality_badge.setText("TEST KOŞULUYOR")
        self.quality_badge.setStyleSheet(f"""
            background-color: rgba(6, 182, 212, 0.15);
            color: {self.accent_color};
            border: 1px solid {self.accent_color};
            border-radius: 4px;
            padding: 2px 6px;
        """)

    def update_result(self, res: SpeedTargetResult):
        self._last_state = "result"
        self._last_res = res
        is_dark = ThemeManager.get_current_theme() == config.THEME_DARK
        colors = ThemeManager.get_colors()
        self._apply_common_theme()

        if res.target_url:
            self.sub_label.setText(f"Hedef: {res.target_url}")

        if res.download_mbps > 0:
            self.speed_val_label.setText(f"{res.download_mbps:.1f} Mbps")
            self.speed_val_label.setStyleSheet(
                f"background: transparent; border: none; color: {self.accent_color}; font-weight: 900;"
            )
        else:
            self.speed_val_label.setText("0.0 Mbps")
            self.speed_val_label.setStyleSheet(
                f"background: transparent; border: none; color: {colors['status_error']}; font-weight: 900;"
            )

        if res.download_mbps >= 30.0:
            badge_bg = "#022c22" if is_dark else "#dcfce7"
            badge_fg = colors["status_success"]
        elif res.download_mbps > 0:
            badge_bg = "#451a03" if is_dark else "#fef3c7"
            badge_fg = colors["status_warning"]
        else:
            badge_bg = "#450a0a" if is_dark else "#fee2e2"
            badge_fg = colors["status_error"]

        self.quality_badge.setText(res.status_desc)
        self.quality_badge.setStyleSheet(f"""
            background-color: {badge_bg};
            color: {badge_fg};
            border: 1px solid {badge_fg};
            border-radius: 4px;
            padding: 2px 8px;
        """)

        self.lbl_rtt_v.setText(f"{res.latency_ms:.1f} ms" if res.latency_ms > 0 else "N/A")
        self.lbl_jit_v.setText(f"{res.jitter_ms:.1f} ms" if res.jitter_ms > 0 else "0.0 ms")
        self.lbl_loss_v.setText(f"%{res.packet_loss_pct:.0f}")
        self.lbl_http_v.setText(f"{res.http_status} OK" if res.http_status in (200, 204, 301, 302) else "Hata")


class SpeedTestView(QWidget):
    """Speed Test main view with dual-stream visual split layout."""

    back_requested = Signal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.engine: Optional[SpeedTestEngine] = None
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

        self.title_lbl = QLabel("Ağ Hız Testi (İç Ağ Hat Kapasitesi & Dış Ağ Throughput)")
        title_font = QFont("DejaVu Sans", 11, QFont.Bold)
        self.title_lbl.setFont(title_font)

        self.summary_badge = QLabel("HAZIR")
        badge_font = QFont("DejaVu Sans Mono", 9, QFont.Bold)
        self.summary_badge.setFont(badge_font)

        self.start_btn = QPushButton("▶ Testi Başlat")
        self.start_btn.setProperty("class", "PrimaryBtn")
        self.start_btn.setFixedHeight(30)
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.clicked.connect(self.start_speed_test)

        header.addWidget(self.back_btn)
        header.addWidget(self.title_lbl)
        header.addStretch()
        header.addWidget(self.summary_badge)
        header.addWidget(self.start_btn)

        # 2. Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setValue(0)

        # 3. Dual Split Cards Layout (Side by side comparison)
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)

        self.internal_card = SpeedColumnCard(
            title="İÇ AĞ (DEÜ KAMPÜS / LAN)",
            subtitle="Hedef: Kampüs Omurga & www.deu.edu.tr",
            accent_color="#10b981",
        )

        self.external_card = SpeedColumnCard(
            title="DIŞ AĞ (İNTERNET / CDN)",
            subtitle="Hedef: Global CDN (Cloudflare / Google)",
            accent_color="#06b6d4",
        )

        cards_layout.addWidget(self.internal_card)
        cards_layout.addWidget(self.external_card)

        # 4. Bottom Footer Info Bar
        self.footer = QFrame()
        self.footer.setFixedHeight(34)
        f_layout = QHBoxLayout(self.footer)
        f_layout.setContentsMargins(12, 0, 12, 0)

        self.footer_label = QLabel(
            "İç ağ: iperf3 / soket tamponu ve paket-treni (packet-train) ile gerçek Gigabit LAN kapasitesini ölçer."
        )
        f_font = QFont("DejaVu Sans Mono", 9)
        self.footer_label.setFont(f_font)

        f_layout.addWidget(self.footer_label)
        f_layout.addStretch()

        main_layout.addLayout(header)
        main_layout.addWidget(self.progress_bar)
        main_layout.addLayout(cards_layout)
        main_layout.addWidget(self.footer)

    def update_theme(self):
        colors = ThemeManager.get_colors()
        self.internal_card.accent_color = colors["status_success"]
        self.external_card.accent_color = colors["accent_cyan"]
        self.title_lbl.setStyleSheet(f"background: transparent; color: {colors['status_success']}; font-weight: 800;")
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {colors['card_bg']};
                border: 1px solid {colors['card_border']};
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {colors['status_success']};
                border-radius: 2px;
            }}
        """)
        self.footer.setStyleSheet(f"""
            QFrame {{
                background-color: {colors['card_bg']};
                border: 1px solid {colors['card_border']};
                border-radius: 8px;
            }}
        """)
        self.footer_label.setStyleSheet(f"background: transparent; color: {colors['text_secondary']};")
        self.summary_badge.setStyleSheet(f"""
            background-color: transparent;
            color: {colors['text_secondary']};
            border: 1px solid {colors['card_border']};
            border-radius: 4px;
            padding: 3px 10px;
        """)
        self.internal_card.update_theme()
        self.external_card.update_theme()

    def start_speed_test(self):
        """Execute non-blocking background speed measurement."""
        colors = ThemeManager.get_colors()
        self.start_btn.setEnabled(False)
        self.summary_badge.setText("TEST EDİLİYOR...")
        self.summary_badge.setStyleSheet(f"""
            background-color: rgba(16, 185, 129, 0.15);
            color: {colors['status_success']};
            border: 1px solid {colors['status_success']};
            border-radius: 4px;
            padding: 3px 10px;
        """)
        self.progress_bar.setValue(10)
        self.internal_card.set_running()
        self.external_card.set_running()

        self.engine = SpeedTestEngine(simulate=False)

        def worker_task():
            def on_prog(msg: str, pct: int):
                self._active_worker.signals.progress.emit(pct)
            return self.engine.run_test(on_progress=on_prog)

        self._active_worker = BaseWorker(worker_task)
        self._active_worker.signals.progress.connect(self.progress_bar.setValue, Qt.QueuedConnection)
        self._active_worker.signals.result.connect(self._on_test_finished, Qt.QueuedConnection)
        self._active_worker.signals.error.connect(self._on_test_error, Qt.QueuedConnection)
        QThreadPool.globalInstance().start(self._active_worker)

    def _on_test_finished(self, report: DualSpeedTestReport):
        is_dark = ThemeManager.get_current_theme() == config.THEME_DARK
        colors = ThemeManager.get_colors()
        self.progress_bar.setValue(100)
        self.start_btn.setEnabled(True)
        self.summary_badge.setText("TAMAMLANDI")
        bg = "#022c22" if is_dark else "#dcfce7"
        fg = colors["status_success"]
        self.summary_badge.setStyleSheet(f"""
            background-color: {bg};
            color: {fg};
            border: 1px solid {fg};
            border-radius: 4px;
            padding: 3px 10px;
        """)

        self.internal_card.update_result(report.internal)
        self.external_card.update_result(report.external)

    def _on_test_error(self, err_tuple):
        is_dark = ThemeManager.get_current_theme() == config.THEME_DARK
        colors = ThemeManager.get_colors()
        self.start_btn.setEnabled(True)
        self.summary_badge.setText("HATA")
        bg = "#450a0a" if is_dark else "#fee2e2"
        fg = colors["status_error"]
        self.summary_badge.setStyleSheet(f"""
            background-color: {bg};
            color: {fg};
            border: 1px solid {fg};
            border-radius: 4px;
            padding: 3px 10px;
        """)
