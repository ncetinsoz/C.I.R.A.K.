"""
6-Item Touch Main Menu View (2 Rows x 3 Columns).
Matches cirak_ui_prototype.html with 240x156 px vector cards.
"""

from typing import List
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
        self.cards: List[MenuCard] = []
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(0)
        main_layout.setAlignment(Qt.AlignCenter)

        grid = QGridLayout()
        grid.setSpacing(12)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setAlignment(Qt.AlignCenter)

        # 1. Otomatik Test (Cyan)
        self.btn_autotest = MenuCard(
            icon_name="lightning",
            title="Otomatik Test",
            description="L1 - L7 Tam Zincir Doğrulama",
            accent_color="#06b6d4",
        )
        self.btn_autotest.clicked.connect(lambda: self.navigate_requested.emit("autotest"))

        # 2. Ağ Keşfi (Indigo)
        self.btn_discovery = MenuCard(
            icon_name="discovery",
            title="Ağ Keşfi",
            description="Switch, Port, VLAN & ARP",
            accent_color="#6366f1",
        )
        self.btn_discovery.clicked.connect(lambda: self.navigate_requested.emit("discovery"))

        # 3. Yetkisiz DHCP (Amber)
        self.btn_rogue = MenuCard(
            icon_name="shield_alert",
            title="Yetkisiz DHCP",
            description="Rogue Avı & Switch Port Tespiti",
            accent_color="#f59e0b",
        )
        self.btn_rogue.clicked.connect(lambda: self.navigate_requested.emit("rogue"))

        # 4. Hız Testi (Emerald)
        self.btn_speed = MenuCard(
            icon_name="speedometer",
            title="Hız Testi",
            description="İç Ağ (DEÜ) & Dış Ağ Throughput",
            accent_color="#10b981",
        )
        self.btn_speed.clicked.connect(lambda: self.navigate_requested.emit("speed"))

        # 5. Kablosuz Ağ (Sky)
        self.btn_wifi = MenuCard(
            icon_name="wifi",
            title="Kablosuz Ağ",
            description="SSID, AP Keşfi & Kanal Yoğunluğu",
            accent_color="#0ea5e9",
        )
        self.btn_wifi.clicked.connect(lambda: self.navigate_requested.emit("wifi"))

        # 6. Ayarlar & Tema (Slate)
        self.btn_settings = MenuCard(
            icon_name="settings",
            title="Ayarlar & Tema",
            description="Aydınlık/Karanlık, IP, Sistem",
            accent_color="#64748b",
        )
        self.btn_settings.clicked.connect(lambda: self.navigate_requested.emit("settings"))

        self.cards = [
            self.btn_autotest, self.btn_discovery, self.btn_rogue,
            self.btn_speed, self.btn_wifi, self.btn_settings,
        ]

        grid.addWidget(self.btn_autotest, 0, 0)
        grid.addWidget(self.btn_discovery, 0, 1)
        grid.addWidget(self.btn_rogue, 0, 2)
        grid.addWidget(self.btn_speed, 1, 0)
        grid.addWidget(self.btn_wifi, 1, 1)
        grid.addWidget(self.btn_settings, 1, 2)

        main_layout.addLayout(grid)

    def update_theme(self):
        """Refresh all card styles when theme toggles."""
        for card in self.cards:
            card.update_style()
