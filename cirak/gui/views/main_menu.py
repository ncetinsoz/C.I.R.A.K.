"""
6-Item Touch Main Menu View (2 Rows x 3 Columns).
Each button is 240 x 160 px, matching the finalized UI specification.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QGridLayout,
    QVBoxLayout,
)
from cirak.gui.components.menu_card import MenuCard


class MainMenuView(QWidget):
    """6'lı dokunmatik ana menü görünümü."""

    navigate_requested = Signal(str)

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setAlignment(Qt.AlignCenter)

        grid = QGridLayout()
        grid.setSpacing(16)
        grid.setAlignment(Qt.AlignCenter)

        # 1. Row 1
        self.btn_autotest = MenuCard(
            icon="⚡",
            title="Otomatik Test",
            description="L1 - L7 Tam Zincir Doğrulama"
        )
        self.btn_autotest.clicked.connect(lambda: self.navigate_requested.emit("autotest"))

        self.btn_discovery = MenuCard(
            icon="🔍",
            title="Ağ Keşfi",
            description="Switch, Port, VLAN & ARP"
        )
        self.btn_discovery.clicked.connect(lambda: self.navigate_requested.emit("discovery"))

        self.btn_rogue = MenuCard(
            icon="🚨",
            title="Yetkisiz DHCP",
            description="Rogue Avı & Switch Port Tespiti"
        )
        self.btn_rogue.clicked.connect(lambda: self.navigate_requested.emit("rogue"))

        # 2. Row 2
        self.btn_speed = MenuCard(
            icon="🚀",
            title="Hız Testi (iPerf3)",
            description="Throughput, Gecikme & Jitter"
        )
        self.btn_speed.clicked.connect(lambda: self.navigate_requested.emit("speed"))

        self.btn_wifi = MenuCard(
            icon="📶",
            title="Kablosuz Ağ",
            description="SSID, AP Keşfi & Kanal Yoğunluğu"
        )
        self.btn_wifi.clicked.connect(lambda: self.navigate_requested.emit("wifi"))

        self.btn_settings = MenuCard(
            icon="⚙️",
            title="Ayarlar & Tema",
            description="Aydınlık/Karanlık, IP, Sistem"
        )
        self.btn_settings.clicked.connect(lambda: self.navigate_requested.emit("settings"))

        # Add to grid: row, col
        grid.addWidget(self.btn_autotest, 0, 0)
        grid.addWidget(self.btn_discovery, 0, 1)
        grid.addWidget(self.btn_rogue, 0, 2)
        grid.addWidget(self.btn_speed, 1, 0)
        grid.addWidget(self.btn_wifi, 1, 1)
        grid.addWidget(self.btn_settings, 1, 2)

        main_layout.addLayout(grid)
