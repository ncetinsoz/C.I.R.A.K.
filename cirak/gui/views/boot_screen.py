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
from cirak.gui.theme import ThemeManager


class BootScreen(QWidget):
    """Boot / Splash screen matching Section 5 design guidelines."""

    boot_completed = Signal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._progress = 0
        self._init_ui()

        # Step timer for smooth boot sequence
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(14)

        # 144x144 Logo
        self.logo_label = QLabel()
        self.logo_label.setFixedSize(144, 144)
        self.logo_label.setScaledContents(True)
        self.update_logo()

        # Title
        title_label = QLabel("Ç.I.R.A.K.")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #22d3ee; font-weight: 900; letter-spacing: 2px;")

        # Subtitle
        sub_label = QLabel("Çok Amaçlı İnceleme, Raporlama ve Ağ Keşif Cihazı")
        sub_label.setAlignment(Qt.AlignCenter)
        sub_label.setStyleSheet("color: #94a3b8; font-size: 11px;")

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedSize(360, 8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setValue(0)

        # Hardware loading status text
        self.status_label = QLabel("Donanım sürücüleri başlatılıyor...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #64748b; font-family: monospace; font-size: 11px;")

        layout.addStretch()
        layout.addWidget(self.logo_label, alignment=Qt.AlignCenter)
        layout.addWidget(title_label, alignment=Qt.AlignCenter)
        layout.addWidget(sub_label, alignment=Qt.AlignCenter)
        layout.addWidget(self.progress_bar, alignment=Qt.AlignCenter)
        layout.addWidget(self.status_label, alignment=Qt.AlignCenter)
        layout.addStretch()

    def update_logo(self):
        theme = ThemeManager.get_current_theme()
        logo_path = config.LOGO_DARK_PATH if theme == config.THEME_DARK else config.LOGO_LIGHT_PATH
        if Path(logo_path).exists():
            self.logo_label.setPixmap(QPixmap(str(logo_path)))

    def start_boot(self):
        """Begin progressive boot simulation."""
        self._progress = 0
        self.timer.start(50)  # ~1.5s total boot time

    def _on_tick(self):
        self._progress += 4
        self.progress_bar.setValue(self._progress)

        if self._progress == 20:
            self.status_label.setText("Modüller yükleniyor: eth0 gigabit PHY hazır...")
        elif self._progress == 50:
            self.status_label.setText("LLDP / CDP paket yakalama motoru başlatıldı...")
        elif self._progress == 80:
            self.status_label.setText("Profil yüklendi: Kampus-Dinamik-DHCP...")
        elif self._progress >= 100:
            self.timer.stop()
            self.status_label.setText("Arayüz hazır. Başlatılıyor...")
            self.boot_completed.emit()
