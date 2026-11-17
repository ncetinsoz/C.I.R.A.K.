"""
Wi-Fi Spectrum & Access Point Analyzer View for Ç.I.R.A.K.
Displays live AP table, 2.4 GHz vs 5 GHz channel congestion,
signal levels, encryption standards, and cleanest channel suggestions.
"""

from typing import List, Optional
from PySide6.QtCore import Qt, Signal, QThreadPool
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)
from cirak import config
from cirak.backend.wifi_scanner import WiFiScanner, WiFiScanReport, WiFiAccessPoint
from cirak.core.worker import BaseWorker


class WiFiView(QWidget):
    """Wi-Fi Environment Scanner view."""

    back_requested = Signal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.scanner = WiFiScanner(simulate=False)
        self.last_report: Optional[WiFiScanReport] = None
        self.current_filter = "ALL"  # "ALL", "2.4", "5"
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

        title = QLabel("Kablosuz Ağ (Wi-Fi 2.4 / 5 GHz Analizörü)")
        title_font = QFont("DejaVu Sans", 11, QFont.Bold)
        title.setFont(title_font)
        title.setStyleSheet("background: transparent; color: #0ea5e9; font-weight: 800;")

        self.ap_count_badge = QLabel("Taranıyor...")
        badge_font = QFont("DejaVu Sans Mono", 9, QFont.Bold)
        self.ap_count_badge.setFont(badge_font)
        self.ap_count_badge.setStyleSheet("""
            background-color: transparent;
            color: #94a3b8;
            border: 1px solid #334155;
            border-radius: 4px;
            padding: 3px 10px;
        """)

        self.rescan_btn = QPushButton("🔄 Yeniden Tara")
        self.rescan_btn.setProperty("class", "PrimaryBtn")
        self.rescan_btn.setFixedHeight(30)
        self.rescan_btn.setCursor(Qt.PointingHandCursor)
        self.rescan_btn.clicked.connect(self.start_scan)

        header.addWidget(self.back_btn)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.ap_count_badge)
        header.addWidget(self.rescan_btn)

        # 2. Filter & Spectrum Summary Bar
        summary_frame = QFrame()
        summary_frame.setFixedHeight(36)
        summary_frame.setStyleSheet("""
            QFrame {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 8px;
            }
        """)
        s_layout = QHBoxLayout(summary_frame)
        s_layout.setContentsMargins(8, 0, 8, 0)
        s_layout.setSpacing(10)

        # Filter buttons
        self.btn_filter_all = QPushButton("Tümü")
        self.btn_filter_all.setFixedHeight(24)
        self.btn_filter_all.clicked.connect(lambda: self._set_filter("ALL"))

        self.btn_filter_24 = QPushButton("2.4 GHz")
        self.btn_filter_24.setFixedHeight(24)
        self.btn_filter_24.clicked.connect(lambda: self._set_filter("2.4"))

        self.btn_filter_5 = QPushButton("5 GHz")
        self.btn_filter_5.setFixedHeight(24)
        self.btn_filter_5.clicked.connect(lambda: self._set_filter("5"))

        s_layout.addWidget(self.btn_filter_all)
        s_layout.addWidget(self.btn_filter_24)
        s_layout.addWidget(self.btn_filter_5)

        divider = QLabel("|")
        divider.setStyleSheet("background: transparent; color: #334155;")
        s_layout.addWidget(divider)

        self.lbl_channel_rec = QLabel("Önerilen 2.4G Kanalı: Kanal 1 (En az çakışma)")
        f_font = QFont("DejaVu Sans Mono", 9)
        self.lbl_channel_rec.setFont(f_font)
        self.lbl_channel_rec.setStyleSheet("background: transparent; color: #10b981; font-weight: bold;")
        s_layout.addWidget(self.lbl_channel_rec)
        s_layout.addStretch()

        self.lbl_connected = QLabel("Bağlı Ağ: Yok")
        self.lbl_connected.setFont(f_font)
        self.lbl_connected.setStyleSheet("background: transparent; color: #38bdf8;")
        s_layout.addWidget(self.lbl_connected)

        # 3. Wi-Fi APs Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Sinyal", "SSID (Ağ Adı)", "Kanal", "Bant", "Güvenlik", "BSSID (MAC)"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)

        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(1, QHeaderView.Stretch)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(5, QHeaderView.ResizeToContents)

        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #0f172a;
                border: 1.5px solid #1e293b;
                border-radius: 8px;
                color: #f8fafc;
                font-family: "DejaVu Sans", sans-serif;
                font-size: 11px;
            }
            QHeaderView::section {
                background-color: #1e293b;
                color: #94a3b8;
                font-weight: 700;
                font-size: 11px;
                border: none;
                padding: 6px;
            }
            QTableWidget::item {
                padding: 4px;
                border-bottom: 1px solid #1e293b;
            }
            QTableWidget::item:selected {
                background-color: #0284c7;
                color: #ffffff;
            }
        """)

        main_layout.addLayout(header)
        main_layout.addWidget(summary_frame)
        main_layout.addWidget(self.table)

        # Trigger initial scan
        self.start_scan()

    def _set_filter(self, filter_mode: str):
        self.current_filter = filter_mode
        self._populate_table()

    def start_scan(self):
        """Execute non-blocking Wi-Fi scan on background thread."""
        self.rescan_btn.setEnabled(False)
        self.rescan_btn.setText("Taranıyor...")
        self.ap_count_badge.setText("Havadaki paketler taranıyor...")

        worker = BaseWorker(self.scanner.scan)
        worker.signals.result.connect(self._on_scan_finished)
        worker.signals.error.connect(self._on_scan_error)
        QThreadPool.globalInstance().start(worker)

    def _on_scan_finished(self, report: WiFiScanReport):
        self.last_report = report
        self.rescan_btn.setEnabled(True)
        self.rescan_btn.setText("🔄 Yeniden Tara")
        self.ap_count_badge.setText(f"{report.total_aps} Erişim Noktası ({report.count_24ghz} @2.4G | {report.count_5ghz} @5G)")

        self.lbl_channel_rec.setText(f"Önerilen 2.4G Kanalı: Kanal {report.best_24ghz_channel} (En az çakışma)")
        if report.connected_ssid:
            self.lbl_connected.setText(f"Bağlı: {report.connected_ssid} ({report.connected_ip or 'IP Yok'})")
        else:
            self.lbl_connected.setText("Bağlı Ağ: Yok")

        self._populate_table()

    def _on_scan_error(self, err_tuple):
        self.rescan_btn.setEnabled(True)
        self.rescan_btn.setText("🔄 Yeniden Tara")
        self.ap_count_badge.setText("Tarama Hatası")

    def _populate_table(self):
        if not self.last_report:
            return

        filtered_aps = []
        for ap in self.last_report.access_points:
            if self.current_filter == "ALL":
                filtered_aps.append(ap)
            elif self.current_filter == "2.4" and ap.band == "2.4 GHz":
                filtered_aps.append(ap)
            elif self.current_filter == "5" and ap.band == "5 GHz":
                filtered_aps.append(ap)

        self.table.setRowCount(len(filtered_aps))

        for row, ap in enumerate(filtered_aps):
            self.table.setRowHeight(row, 32)

            # Signal Item
            signal_color = "#10b981" if ap.signal_pct >= 70 else ("#f59e0b" if ap.signal_pct >= 40 else "#ef4444")
            item_sig = QTableWidgetItem(f"{ap.signal_dbm} dBm (%{ap.signal_pct})")
            item_sig.setForeground(QColor(signal_color))
            item_sig.setFont(QFont("DejaVu Sans Mono", 10, QFont.Bold))

            # SSID Item
            prefix = "● " if ap.is_connected else ""
            item_ssid = QTableWidgetItem(f"{prefix}{ap.ssid}")
            item_ssid.setFont(QFont("DejaVu Sans", 11, QFont.Bold if ap.is_connected else QFont.Normal))
            if ap.is_connected:
                item_ssid.setForeground(QColor("#38bdf8"))

            # Channel
            item_chan = QTableWidgetItem(f"Kanal {ap.channel}")
            item_chan.setTextAlignment(Qt.AlignCenter)
            item_chan.setFont(QFont("DejaVu Sans Mono", 10))

            # Band
            band_color = "#0ea5e9" if ap.band == "5 GHz" else "#f59e0b"
            item_band = QTableWidgetItem(ap.band)
            item_band.setTextAlignment(Qt.AlignCenter)
            item_band.setForeground(QColor(band_color))
            item_band.setFont(QFont("DejaVu Sans Mono", 10, QFont.Bold))

            # Security
            item_sec = QTableWidgetItem(ap.security)
            item_sec.setFont(QFont("DejaVu Sans", 10))

            # BSSID (MAC)
            item_mac = QTableWidgetItem(ap.bssid)
            item_mac.setFont(QFont("DejaVu Sans Mono", 9))
            item_mac.setForeground(QColor("#94a3b8"))

            self.table.setItem(row, 0, item_sig)
            self.table.setItem(row, 1, item_ssid)
            self.table.setItem(row, 2, item_chan)
            self.table.setItem(row, 3, item_band)
            self.table.setItem(row, 4, item_sec)
            self.table.setItem(row, 5, item_mac)
