"""
Touch-Optimized Menu Card (240 x 156 px) for Ç.I.R.A.K. Handheld.
Faithfully recreates the modern industrial UI from cirak_ui_prototype.html.
Features top-left vector SVG icon badge, bottom-left typography, and tactile touch feedback.
"""

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont, QColor, QPainter, QCursor
from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QWidget,
)
from cirak import config
from cirak.gui.icons import get_svg_pixmap
from cirak.gui.theme import ThemeManager


class MenuCard(QFrame):
    """240 x 156 px modern touch card button."""

    clicked = Signal()

    def __init__(
        self,
        icon_name: str,
        title: str,
        description: str,
        accent_color: str,
        parent: QWidget = None
    ):
        super().__init__(parent)
        self.icon_name = icon_name
        self.title_text = title
        self.desc_text = description
        self.accent_color = accent_color
        self._is_pressed = False

        self.setObjectName("MenuCard")
        self.setFixedSize(config.MENU_BUTTON_WIDTH, config.MENU_BUTTON_HEIGHT)
        self.setCursor(Qt.PointingHandCursor)
        self._init_ui()
        self.update_style()

    def _init_ui(self):
        # Card outer layout: p-4 (14px padding)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(0)

        # 1. Top Section: Icon Badge (42x42 px, rounded-xl)
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)

        self.icon_badge = QFrame()
        self.icon_badge.setObjectName("MenuCardBadge")
        self.icon_badge.setFixedSize(42, 42)
        badge_layout = QVBoxLayout(self.icon_badge)
        badge_layout.setContentsMargins(0, 0, 0, 0)
        badge_layout.setAlignment(Qt.AlignCenter)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(24, 24)
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet("background: transparent; border: none;")
        badge_layout.addWidget(self.icon_label)

        top_row.addWidget(self.icon_badge)
        top_row.addStretch()

        # 2. Breathing Room
        layout.addLayout(top_row)
        layout.addStretch()

        # 3. Bottom Section: Left-aligned Title & Description
        bottom_box = QVBoxLayout()
        bottom_box.setContentsMargins(0, 0, 0, 0)
        bottom_box.setSpacing(2)

        self.title_label = QLabel(self.title_text)
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_font.setWeight(QFont.ExtraBold)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet("background: transparent; border: none; color: #ffffff; font-weight: 800;")

        self.desc_label = QLabel(self.desc_text)
        desc_font = QFont()
        desc_font.setPointSize(9)
        self.desc_label.setFont(desc_font)
        self.desc_label.setStyleSheet("background: transparent; border: none; color: #94a3b8;")
        self.desc_label.setWordWrap(True)

        bottom_box.addWidget(self.title_label)
        bottom_box.addWidget(self.desc_label)

        layout.addLayout(bottom_box)

    def update_style(self):
        """Update card styles and icon pixmap based on active theme and accent color."""
        is_dark = ThemeManager.get_current_theme() == config.THEME_DARK
        card_bg = "#0f172a" if is_dark else "#ffffff"
        title_color = "#ffffff" if is_dark else "#0f172a"
        desc_color = "#94a3b8" if is_dark else "#64748b"

        # Accent color hex to rgba for badge
        c = QColor(self.accent_color)
        badge_bg = f"rgba({c.red()}, {c.green()}, {c.blue()}, 0.15)"
        badge_border = f"rgba({c.red()}, {c.green()}, {c.blue()}, 0.35)"

        self.setStyleSheet(f"""
            QFrame#MenuCard {{
                background-color: {card_bg};
                border: 2px solid {self.accent_color};
                border-radius: 12px;
            }}
            #MenuCard QLabel {{
                background: transparent;
                border: none;
            }}
        """)

        self.icon_badge.setStyleSheet(f"""
            QFrame#MenuCardBadge {{
                background-color: {badge_bg};
                border: 1px solid {badge_border};
                border-radius: 10px;
            }}
        """)

        self.title_label.setStyleSheet(f"background: transparent; border: none; color: {title_color}; font-weight: 800;")
        self.desc_label.setStyleSheet(f"background: transparent; border: none; color: {desc_color};")

        # Render vector SVG icon
        pix = get_svg_pixmap(self.icon_name, color=self.accent_color, size=24)
        self.icon_label.setPixmap(pix)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_pressed = True
            is_dark = ThemeManager.get_current_theme() == config.THEME_DARK
            pressed_bg = "#1e293b" if is_dark else "#f1f5f9"
            self.setStyleSheet(f"""
                QFrame#MenuCard {{
                    background-color: {pressed_bg};
                    border: 2.5px solid {self.accent_color};
                    border-radius: 12px;
                }}
                #MenuCard QLabel {{
                    background: transparent;
                    border: none;
                }}
            """)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._is_pressed:
            self._is_pressed = False
            self.update_style()
            self.clicked.emit()
        super().mouseReleaseEvent(event)
