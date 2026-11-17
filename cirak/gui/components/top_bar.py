"""
Top Status Bar (40 px height) for Ç.I.R.A.K. Handheld.
Includes ÇIRAK Amblem, Device Name, Profile, Ethernet Link, Wi-Fi, Power, and Live Clock.
"""

from datetime import datetime
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap, QFont, QColor, QPainter, QBrush, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)
from cirak import config
from cirak.gui.theme import ThemeManager


class TopBar(QFrame):
    """Fixed 40px top status bar."""

    theme_toggled = Signal(str)

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("TopBar")
        self.setFixedHeight(config.TOP_BAR_HEIGHT)
        self._eth_connected = True
        self._wifi_connected = True
        self._init_ui()

        # 1-second clock timer
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)
        self._update_clock()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(10)

        # 1. Left Section: Logo, Title, Profile
        self.logo_label = QLabel()
        self.logo_label.setFixedSize(30, 30)
        self.logo_label.setScaledContents(True)
        self.update_logo()

        self.title_label = QLabel("Ç.I.R.A.K.")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet("color: #22d3ee; font-weight: 900;")

        self.profile_label = QLabel(f"Profil: {config.DEFAULT_PROFILE}")
        profile_font = QFont()
        profile_font.setPointSize(9)
        self.profile_label.setFont(profile_font)
        self.profile_label.setStyleSheet("color: #f59e0b; font-weight: 600;")

        layout.addWidget(self.logo_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.profile_label)

        layout.addStretch()

        # 2. Right Section: Ethernet, Wi-Fi, Power, Clock, Theme Toggle
        # Ethernet Status Indicator (Solid Green / Solid Red - Wikimedia standard)
        self.eth_indicator = QLabel()
        self.update_eth_indicator(self._eth_connected)

        # Wi-Fi Status Indicator
        self.wifi_indicator = QLabel("📶")
        self.wifi_indicator.setStyleSheet("color: #10b981; font-size: 13px;")

        # Power Status Indicator
        self.power_label = QLabel("⚡ 5.1V %94")
        self.power_label.setStyleSheet("color: #38bdf8; font-family: monospace; font-size: 11px; font-weight: bold;")

        # Monospace Live Digital Clock
        self.clock_label = QLabel("00:00:00")
        self.clock_label.setStyleSheet("color: #94a3b8; font-family: monospace; font-size: 11px; font-weight: bold;")

        # Theme toggle button
        self.theme_btn = QPushButton("◐")
        self.theme_btn.setFixedSize(32, 28)
        self.theme_btn.setToolTip("Tema Değiştir (Aydınlık / Karanlık)")
        self.theme_btn.clicked.connect(self._on_theme_toggle_clicked)

        layout.addWidget(self.eth_indicator)
        layout.addWidget(self.wifi_indicator)
        layout.addWidget(self.power_label)
        layout.addWidget(self.clock_label)
        layout.addWidget(self.theme_btn)

    def update_logo(self):
        """Update logo image based on theme."""
        theme = ThemeManager.get_current_theme()
        logo_path = config.LOGO_DARK_PATH if theme == config.THEME_DARK else config.LOGO_LIGHT_PATH
        if Path(logo_path).exists():
            pix = QPixmap(str(logo_path))
            self.logo_label.setPixmap(pix)

    def update_eth_indicator(self, connected: bool, speed_mbps: int = 1000):
        """Update ethernet link icon (Solid Green when up, Solid Red when down)."""
        self._eth_connected = connected
        color = "#10b981" if connected else "#ef4444"
        text = f"🔌 eth0 {speed_mbps}M" if connected else "🔌 eth0 Link Yok"
        self.eth_indicator.setText(text)
        self.eth_indicator.setStyleSheet(
            f"color: {color}; font-weight: 800; font-size: 11px; "
            f"background: {'#064e3b' if connected else '#450a0a'}; "
            f"border: 1px solid {color}; border-radius: 4px; padding: 2px 6px;"
        )

    def _update_clock(self):
        now = datetime.now().strftime("%H:%M:%S")
        self.clock_label.setText(now)

    def _on_theme_toggle_clicked(self):
        new_theme = ThemeManager.toggle_theme()
        self.update_logo()
        self.theme_toggled.emit(new_theme)
