"""
Touch-Optimized Menu Card (240 x 160 px) for Ç.I.R.A.K. Handheld.
Designed specifically for finger / glove touch operation on 7" capacitive display.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QLabel,
    QWidget,
)
from cirak import config


class MenuCard(QFrame):
    """240 x 160 px touch card button."""

    clicked = Signal()

    def __init__(
        self,
        icon: str,
        title: str,
        description: str,
        parent: QWidget = None
    ):
        super().__init__(parent)
        self.setProperty("class", "MenuCard")
        self.setFixedSize(config.MENU_BUTTON_WIDTH, config.MENU_BUTTON_HEIGHT)
        self.setCursor(Qt.PointingHandCursor)
        self.title_text = title
        self._init_ui(icon, title, description)

    def _init_ui(self, icon: str, title: str, description: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignCenter)

        # Icon
        self.icon_label = QLabel(icon)
        icon_font = QFont()
        icon_font.setPointSize(28)
        self.icon_label.setFont(icon_font)
        self.icon_label.setAlignment(Qt.AlignCenter)

        # Title
        self.title_label = QLabel(title)
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-weight: 800;")

        # Description
        self.desc_label = QLabel(description)
        desc_font = QFont()
        desc_font.setPointSize(10)
        self.desc_label.setFont(desc_font)
        self.desc_label.setAlignment(Qt.AlignCenter)
        self.desc_label.setStyleSheet("color: #94a3b8;")
        self.desc_label.setWordWrap(True)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.desc_label)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
