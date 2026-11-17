"""
Minimalist Industrial Boot / Splash Screen.
Displays 144x144 ÇIRAK logo, hardware module loading bar, and transitions to Main Menu.
"""

from pathlib import Path
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
        title_label = QLabel("Ç.I.R.A.K.")
        title_font = QFont("DejaVu Sans Mono", 24, QFont.Bold)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("background: transparent; color: #22d3ee; font-weight: 900; letter-spacing: 3px;")

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedSize(360, 6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background-color: #22d3ee;
                border-radius: 2px;
            }
        """)

        layout.addStretch()
        layout.addWidget(self.logo_label, alignment=Qt.AlignCenter)
        layout.addSpacing(8)
        layout.addWidget(title_label, alignment=Qt.AlignCenter)
        layout.addSpacing(20)
        layout.addWidget(self.progress_bar, alignment=Qt.AlignCenter)
        layout.addStretch()

    def update_logo(self):
        logo_path = config.LOGO_PATH
        if not logo_path.exists():
            logo_path = config.LOGO_LIGHT_PATH
        if logo_path.exists():
            pix = QPixmap(str(logo_path))
            scaled_pix = pix.scaled(144, 144, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.logo_label.setPixmap(scaled_pix)

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
