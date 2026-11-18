"""
Top Status Bar (40 px height) for Ç.I.R.A.K. Handheld.
Faithfully recreates the top bar from cirak_ui_prototype.html with pure vector icons and no visual clutter.
"""

from datetime import datetime
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap, QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)
from cirak import config
from cirak.gui.icons import get_svg_pixmap
from cirak.gui.theme import ThemeManager


class TopBar(QFrame):
    """Fixed 40px top status bar with vector indicators and real network telemetry."""

    theme_toggled = Signal(str)

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("TopBar")
        self.setFixedHeight(config.TOP_BAR_HEIGHT)
        self._eth_connected = False
        self._eth_speed = 0
        self._wifi_connected = False
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

        # ==========================================
        # 1. Left Section: Logo, Title, Profile
        # ==========================================
        left_box = QHBoxLayout()
        left_box.setContentsMargins(0, 0, 0, 0)
        left_box.setSpacing(8)

        # Official Logo (26x26 smoothly scaled)
        self.logo_label = QLabel()
        self.logo_label.setFixedSize(26, 26)
        self.logo_label.setStyleSheet("background: transparent;")
        self.update_logo()

        # Title: Ç.I.R.A.K.
        self.title_label = QLabel("Ç.I.R.A.K.")
        title_font = QFont("DejaVu Sans Mono", 11, QFont.ExtraBold)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet("background: transparent; color: #22d3ee; font-weight: 900;")

        # Divider
        self.divider_label = QLabel("|")
        self.divider_label.setStyleSheet("background: transparent; color: #334155; font-weight: bold;")

        # Profile
        self.profile_lbl = QLabel("Profil:")
        self.profile_lbl.setStyleSheet("background: transparent; color: #64748b; font-size: 11px;")

        self.profile_val = QLabel(config.DEFAULT_PROFILE)
        prof_font = QFont("DejaVu Sans Mono", 9, QFont.Bold)
        self.profile_val.setFont(prof_font)
        self.profile_val.setStyleSheet("background: transparent; color: #f59e0b; font-weight: 700;")

        left_box.addWidget(self.logo_label)
        left_box.addWidget(self.title_label)
        left_box.addWidget(self.divider_label)
        left_box.addWidget(self.profile_lbl)
        left_box.addWidget(self.profile_val)

        layout.addLayout(left_box)
        layout.addStretch()

        # ==========================================
        # 2. Right Section: Ethernet, Wi-Fi, Power, Clock, Theme
        # ==========================================
        right_box = QHBoxLayout()
        right_box.setContentsMargins(0, 0, 0, 0)
        right_box.setSpacing(12)

        # Ethernet Status (3-node LAN port SVG icon + speed label)
        self.eth_box = QHBoxLayout()
        self.eth_box.setContentsMargins(0, 0, 0, 0)
        self.eth_box.setSpacing(4)

        self.eth_icon_label = QLabel()
        self.eth_icon_label.setFixedSize(18, 18)
        self.eth_icon_label.setStyleSheet("background: transparent;")

        self.eth_text_label = QLabel("eth0")
        eth_font = QFont("DejaVu Sans Mono", 9, QFont.Bold)
        self.eth_text_label.setFont(eth_font)
        self.eth_text_label.setStyleSheet("background: transparent;")

        self.eth_box.addWidget(self.eth_icon_label)
        self.eth_box.addWidget(self.eth_text_label)

        # Wi-Fi Status (Vector SVG icon)
        self.wifi_icon_label = QLabel()
        self.wifi_icon_label.setFixedSize(18, 18)
        self.wifi_icon_label.setStyleSheet("background: transparent;")

        # Power Status (Lightning SVG + voltage text)
        self.power_box = QHBoxLayout()
        self.power_box.setContentsMargins(0, 0, 0, 0)
        self.power_box.setSpacing(3)

        self.power_icon = QLabel()
        self.power_icon.setFixedSize(14, 14)
        self.power_icon.setStyleSheet("background: transparent;")
        self.power_icon.setPixmap(get_svg_pixmap("power_bolt", color="#f59e0b", size=14))

        self.power_val = QLabel("5.1V %94")
        pwr_font = QFont("DejaVu Sans Mono", 9, QFont.Bold)
        self.power_val.setFont(pwr_font)
        self.power_val.setStyleSheet("background: transparent; color: #10b981; font-weight: 700;")

        self.power_box.addWidget(self.power_icon)
        self.power_box.addWidget(self.power_val)

        # Live Digital Monospace Clock
        self.clock_label = QLabel("00:00:00")
        clock_font = QFont("DejaVu Sans Mono", 10, QFont.Bold)
        self.clock_label.setFont(clock_font)
        self.clock_label.setStyleSheet("background: transparent; color: #f8fafc; font-weight: 700;")

        right_box.addLayout(self.eth_box)
        right_box.addWidget(self.wifi_icon_label)
        right_box.addLayout(self.power_box)
        right_box.addWidget(self.clock_label)

        layout.addLayout(right_box)

        # Set initial network telemetry
        self.update_eth_status(connected=False, speed_mbps=0)
        self.update_wifi_status(connected=False)

    def update_logo(self):
        """Update logo using official high-res PNG."""
        logo_path = config.LOGO_PATH
        if not logo_path.exists():
            logo_path = config.LOGO_LIGHT_PATH

        if logo_path.exists():
            pix = QPixmap(str(logo_path))
            scaled_pix = pix.scaled(26, 26, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.logo_label.setPixmap(scaled_pix)

    def update_eth_status(self, connected: bool, speed_mbps: int = 1000):
        """Update 3-node ethernet port vector icon and speed text."""
        self._eth_connected = connected
        self._eth_speed = speed_mbps

        color = "#10b981" if connected else "#ef4444"
        text = f"eth0 {speed_mbps}M" if (connected and speed_mbps > 0) else ("eth0 UP" if connected else "eth0 Link Yok")

        pix = get_svg_pixmap("ethernet_port", color=color, size=18)
        self.eth_icon_label.setPixmap(pix)
        self.eth_text_label.setText(text)
        self.eth_text_label.setStyleSheet(f"background: transparent; color: {color}; font-weight: 700;")

    def update_wifi_status(self, connected: bool = True):
        """Update Wi-Fi vector icon."""
        self._wifi_connected = connected
        color = "#22d3ee" if connected else "#64748b"
        pix = get_svg_pixmap("wifi", color=color, size=18)
        self.wifi_icon_label.setPixmap(pix)

    def update_theme_icon(self):
        """No-op kept for compatibility; theme selection moved to Settings view."""
        pass

    def _update_clock(self):
        now = datetime.now().strftime("%H:%M:%S")
        self.clock_label.setText(now)

    def set_profile_name(self, name: str):
        self.profile_val.setText(name)
