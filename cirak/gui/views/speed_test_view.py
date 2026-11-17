"""
Dual-Stream Speed Test View for Ç.I.R.A.K.
Side-by-side comparison of:
  - Internal Network (DEÜ Campus / www.deu.edu.tr)
  - External Network (Global Internet CDN / Cloudflare)
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
        self.title_label.setStyleSheet(f"background: transparent; border: none; color: {self.accent_color}; font-weight: 800;")

        self.sub_label = QLabel(self.subtitle_text)
        s_font = QFont("DejaVu Sans Mono", 9)
        self.sub_label.setFont(s_font)
        self.sub_label.setStyleSheet("background: transparent; border: none; color: #94a3b8;")

        header_box.addWidget(self.title_label)
        header_box.addWidget(self.sub_label)
        layout.addLayout(header_box)

        # Large Digital Speed Value
        self.speed_val_label = QLabel("-- Mbps")
        val_font = QFont("DejaVu Sans Mono", 24, QFont.Bold)
        self.speed_val_label.setFont(val_font)
        self.speed_val_label.setAlignment(Qt.AlignCenter)
        self.speed_val_label.setStyleSheet(f"background: transparent; border: none; color: #f8fafc; font-weight: 900;")
        layout.addWidget(self.speed_val_label)

        # Status badge below speed
        self.quality_badge = QLabel("BEKLİYOR")
        b_font = QFont("DejaVu Sans Mono", 9, QFont.Bold)
        self.quality_badge.setFont(b_font)
        self.quality_badge.setAlignment(Qt.AlignCenter)
        self.quality_badge.setFixedHeight(22)
        self.quality_badge.setStyleSheet("""
            background-color: transparent;
            color: #64748b;
            border: 1px solid #334155;
            border-radius: 4px;
            padding: 2px 6px;
        """)
        layout.addWidget(self.quality_badge)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("background-color: #1e293b; max-height: 1px;")
        layout.addWidget(divider)

        # Metrics Details Grid (2 columns x 2 rows)
        grid = QGridLayout()
        grid.setSpacing(6)
        grid.setContentsMargins(0, 4, 0, 4)

        # Row 1: RTT Latency & Jitter
        lbl_rtt_t = QLabel("Gecikme (RTT):")
        lbl_rtt_t.setStyleSheet("background: transparent; border: none; color: #64748b; font-size: 11px;")
        self.lbl_rtt_v = QLabel("-- ms")
        self.lbl_rtt_v.setStyleSheet("background: transparent; border: none; color: #cbd5e1; font-family: monospace; font-weight: bold; font-size: 11px;")

        lbl_jit_t = QLabel("Jitter:")
        lbl_jit_t.setStyleSheet("background: transparent; border: none; color: #64748b; font-size: 11px;")
        self.lbl_jit_v = QLabel("-- ms")
        self.lbl_jit_v.setStyleSheet("background: transparent; border: none; color: #cbd5e1; font-family: monospace; font-weight: bold; font-size: 11px;")

        # Row 2: Packet Loss & HTTP Status
        lbl_loss_t = QLabel("Paket Kaybı:")
        lbl_loss_t.setStyleSheet("background: transparent; border: none; color: #64748b; font-size: 11px;")
        self.lbl_loss_v = QLabel("-- %")
        self.lbl_loss_v.setStyleSheet("background: transparent; border: none; color: #cbd5e1; font-family: monospace; font-weight: bold; font-size: 11px;")

        lbl_http_t = QLabel("HTTP Yanıt:")
        lbl_http_t.setStyleSheet("background: transparent; border: none; color: #64748b; font-size: 11px;")
        self.lbl_http_v = QLabel("--")
        self.lbl_http_v.setStyleSheet("background: transparent; border: none; color: #cbd5e1; font-family: monospace; font-weight: bold; font-size: 11px;")

        grid.addWidget(lbl_rtt_t, 0, 0)
        grid.addWidget(self.lbl_rtt_v, 0, 1)
        grid.addWidget(lbl_jit_t, 0, 2)
        grid.addWidget(self.lbl_jit_v, 0, 3)

        grid.addWidget(lbl_loss_t, 1, 0)
        grid.addWidget(self.lbl_loss_v, 1, 1)
        grid.addWidget(lbl_http_t, 1, 2)
        grid.addWidget(self.lbl_http_v, 1, 3)

        layout.addLayout(grid)
        layout.addStretch()

    def reset_card(self):
        is_dark = ThemeManager.get_current_theme() == config.THEME_DARK
        card_bg = "#0f172a" if is_dark else "#ffffff"
        self.setStyleSheet(f"""
            QFrame#SpeedColumnCard {{
                background-color: {card_bg};
                border: 1.5px solid {self.accent_color};
                border-radius: 12px;
            }}
            #SpeedColumnCard QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        self.speed_val_label.setText("-- Mbps")
        self.speed_val_label.setStyleSheet("background: transparent; border: none; color: #64748b; font-weight: 900;")
        self.quality_badge.setText("BEKLİYOR")
        self.quality_badge.setStyleSheet("""
            background-color: transparent;
            color: #64748b;
            border: 1px solid #334155;
            border-radius: 4px;
            padding: 2px 6px;
        """)
        self.lbl_rtt_v.setText("-- ms")
        self.lbl_jit_v.setText("-- ms")
        self.lbl_loss_v.setText("-- %")
        self.lbl_http_v.setText("--")

    def set_running(self):
        self.speed_val_label.setText("ÖLÇÜLÜYOR...")
        self.speed_val_label.setStyleSheet(f"background: transparent; border: none; color: {self.accent_color}; font-weight: 800; font-size: 18px;")
        self.quality_badge.setText("TEST KOŞULUYOR")
        self.quality_badge.setStyleSheet(f"""
            background-color: rgba(6, 182, 212, 0.15);
            color: {self.accent_color};
            border: 1px solid {self.accent_color};
            border-radius: 4px;
            padding: 2px 6px;
        """)

    def update_result(self, res: SpeedTargetResult):
        # Format Speed
        if res.download_mbps > 0:
            self.speed_val_label.setText(f"{res.download_mbps:.1f} Mbps")
            self.speed_val_label.setStyleSheet(f"background: transparent; border: none; color: {self.accent_color}; font-weight: 900;")
        else:
            self.speed_val_label.setText("0.0 Mbps")
            self.speed_val_label.setStyleSheet("background: transparent; border: none; color: #ef4444; font-weight: 900;")

        # Quality badge
        badge_bg = "#022c22" if res.download_mbps >= 30.0 else ("#451a03" if res.download_mbps > 0 else "#450a0a")
        badge_fg = "#10b981" if res.download_mbps >= 30.0 else ("#f59e0b" if res.download_mbps > 0 else "#ef4444")
        self.quality_badge.setText(res.status_desc)
        self.quality_badge.setStyleSheet(f"""
            background-color: {badge_bg};
            color: {badge_fg};
            border: 1px solid {badge_fg};
            border-radius: 4px;
            padding: 2px 8px;
        """)

        # Metrics
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

        title = QLabel("Ağ Hız Testi (İç Ağ & Dış Ağ Throughput)")
        title_font = QFont("DejaVu Sans", 11, QFont.Bold)
        title.setFont(title_font)
        title.setStyleSheet("background: transparent; color: #10b981; font-weight: 800;")

        self.summary_badge = QLabel("HAZIR")
        badge_font = QFont("DejaVu Sans Mono", 9, QFont.Bold)
        self.summary_badge.setFont(badge_font)
        self.summary_badge.setStyleSheet("""
            background-color: transparent;
            color: #94a3b8;
            border: 1px solid #334155;
            border-radius: 4px;
            padding: 3px 10px;
        """)

        self.start_btn = QPushButton("▶ Testi Başlat")
        self.start_btn.setProperty("class", "PrimaryBtn")
        self.start_btn.setFixedHeight(30)
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.clicked.connect(self.start_speed_test)

        header.addWidget(self.back_btn)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.summary_badge)
        header.addWidget(self.start_btn)

        # 2. Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #10b981;
                border-radius: 2px;
            }
        """)

        # 3. Dual Split Cards Layout (Side by side comparison)
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)

        # Left Card: Internal DEÜ Campus Network
        self.internal_card = SpeedColumnCard(
            title="İÇ AĞ (DEÜ KAMPÜS)",
            subtitle="Hedef: www.deu.edu.tr (Kurumsal Sunucu)",
            accent_color="#10b981",
        )

        # Right Card: External Global Internet CDN
        self.external_card = SpeedColumnCard(
            title="DIŞ AĞ (İNTERNET / CDN)",
            subtitle="Hedef: Global CDN (Cloudflare / Google)",
            accent_color="#06b6d4",
        )

        cards_layout.addWidget(self.internal_card)
        cards_layout.addWidget(self.external_card)

        # 4. Bottom Footer Info Bar
        footer = QFrame()
        footer.setFixedHeight(34)
        footer.setStyleSheet("""
            QFrame {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 8px;
            }
        """)
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(12, 0, 12, 0)

        self.footer_label = QLabel("İç ağ doğrudan yerel kurumsal kampüs sunucusuna, dış ağ ulusal/global CDN noktasına test edilir.")
        f_font = QFont("DejaVu Sans Mono", 9)
        self.footer_label.setFont(f_font)
        self.footer_label.setStyleSheet("background: transparent; color: #94a3b8;")

        f_layout.addWidget(self.footer_label)
        f_layout.addStretch()

        main_layout.addLayout(header)
        main_layout.addWidget(self.progress_bar)
        main_layout.addLayout(cards_layout)
        main_layout.addWidget(footer)

    def start_speed_test(self):
        """Execute non-blocking background speed measurement."""
        self.start_btn.setEnabled(False)
        self.summary_badge.setText("TEST EDİLİYOR...")
        self.summary_badge.setStyleSheet("""
            background-color: rgba(16, 185, 129, 0.15);
            color: #10b981;
            border: 1px solid #10b981;
            border-radius: 4px;
            padding: 3px 10px;
        """)
        self.progress_bar.setValue(10)
        self.internal_card.set_running()
        self.external_card.set_running()

        self.engine = SpeedTestEngine(simulate=False)

        def worker_task():
            def on_prog(msg: str, pct: int):
                self.progress_bar.setValue(pct)
            return self.engine.run_test(on_progress=on_prog)

        worker = BaseWorker(worker_task)
        worker.signals.result.connect(self._on_test_finished)
        worker.signals.error.connect(self._on_test_error)
        QThreadPool.globalInstance().start(worker)

    def _on_test_finished(self, report: DualSpeedTestReport):
        self.progress_bar.setValue(100)
        self.start_btn.setEnabled(True)
        self.summary_badge.setText("TAMAMLANDI")
        self.summary_badge.setStyleSheet("""
            background-color: #022c22;
            color: #10b981;
            border: 1px solid #10b981;
            border-radius: 4px;
            padding: 3px 10px;
        """)

        self.internal_card.update_result(report.internal)
        self.external_card.update_result(report.external)

    def _on_test_error(self, err_tuple):
        self.start_btn.setEnabled(True)
        self.summary_badge.setText("HATA")
        self.summary_badge.setStyleSheet("""
            background-color: #450a0a;
            color: #ef4444;
            border: 1px solid #ef4444;
            border-radius: 4px;
            padding: 3px 10px;
        """)
