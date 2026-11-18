"""
Minimalist Industrial Boot / Splash Screen.
Displays 144x144 ÇIRAK logo (dark logo in Dark Mode, light logo in Light Mode),
hardware module loading bar, and transitions to Main Menu.
"""

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap, QFont
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QProgressBar,
)
from cirak import config
from cirak.backend.network_detector import NetworkDetector
from cirak.gui.theme import ThemeManager


class BootScreen(QWidget):
    """Boot / Splash screen matching Section 5 design guidelines."""

    boot_completed = Signal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._progress = 0
        self._active_iface = NetworkDetector.get_active_interface()
        self._init_ui()
        self.update_theme()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(12)

        # 144x144 Official Logo
        self.logo_label = QLabel()
        self.logo_label.setFixedSize(144, 144)
        self.logo_label.setAlignment(Qt.AlignCenter)
        self.logo_label.setStyleSheet("background: transparent;")
        self.update_logo()

        # Title
        self.title_label = QLabel("Ç.I.R.A.K.")
        title_font = QFont("DejaVu Sans Mono", 24, QFont.Bold)
        self.title_label.setFont(title_font)
        self.title_label.setAlignment(Qt.AlignCenter)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedSize(360, 6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setValue(0)

        layout.addStretch()
        layout.addWidget(self.logo_label, alignment=Qt.AlignCenter)
        layout.addSpacing(8)
        layout.addWidget(self.title_label, alignment=Qt.AlignCenter)
        layout.addSpacing(20)
        layout.addWidget(self.progress_bar, alignment=Qt.AlignCenter)
        layout.addStretch()

    def update_logo(self):
        """Use dark obsidian logo in Dark Mode and light logo in Light Mode."""
        is_dark = ThemeManager.get_current_theme() == config.THEME_DARK
        logo_path = config.LOGO_DARK_PATH if is_dark else config.LOGO_LIGHT_PATH
        if not logo_path.exists():
            logo_path = config.LOGO_PATH
        if logo_path.exists():
            pix = QPixmap(str(logo_path))
            scaled_pix = pix.scaled(144, 144, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.logo_label.setPixmap(scaled_pix)

    def update_theme(self):
        is_dark = ThemeManager.get_current_theme() == config.THEME_DARK
        colors = ThemeManager.get_colors()
        self.update_logo()
        accent = "#22d3ee" if is_dark else "#0369a1"
        self.title_label.setStyleSheet(
            f"background: transparent; color: {accent}; font-weight: 900; letter-spacing: 3px;"
        )
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {colors['card_bg']};
                border: 1px solid {colors['card_border']};
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: {accent};
                border-radius: 2px;
            }}
        """)

    def start_boot(self):
        """Begin progressive boot sequence."""
        self._progress = 0
        self.timer.start(40)  # ~1s smooth progression

    def _on_tick(self):
        self._progress += 4
        self.progress_bar.setValue(min(self._progress, 100))

        if self._progress >= 100:
            self.timer.stop()
            self.boot_completed.emit()
