"""
Top Status Bar (40 px height) for Ç.I.R.A.K. Handheld.
Includes:
- Theme-aware Official Logo (cirak_logo_dark.jpg in Dark Mode, cirak_logo.png in Light Mode)
- Active Profile Indicator
- Live Ethernet & Wi-Fi Vector Status Indicators
- Monospace Digital Clock
- Safe Power Off / Reboot Button & Confirmation Modal (microSD ext4 protection)
"""

from datetime import datetime
import os
import subprocess
from PySide6.QtCore import Qt, QTimer, Signal, QSize
from PySide6.QtGui import QPixmap, QFont, QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
    QDialog,
)
from cirak import config
from cirak.gui.icons import get_svg_pixmap
from cirak.gui.theme import ThemeManager


class PowerDialog(QDialog):
    """Touch-optimized Safe Shutdown / Reboot modal to protect microSD ext4 filesystem."""

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle("Güvenli Kapatma / Yeniden Başlatma")
        self.setFixedSize(460, 250)
        self.setModal(True)
        self._init_ui()

    def _init_ui(self):
        is_dark = ThemeManager.get_current_theme() == config.THEME_DARK
        colors = ThemeManager.get_colors()
        bg = "#0f172a" if is_dark else "#e2e8f0"
        border = "#ef4444" if is_dark else "#b91c1c"
        text_pri = colors["text_primary"]
        text_sec = colors["text_secondary"]

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg};
                border: 2px solid {border};
                border-radius: 12px;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        # Header
        hdr = QHBoxLayout()
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(26, 26)
        icon_lbl.setPixmap(get_svg_pixmap("power_off", color="#ef4444", size=24))

        title = QLabel("Sistem Güç Yönetimi (Güvenli Kapatma)")
        title.setFont(QFont("DejaVu Sans", 12, QFont.Bold))
        title.setStyleSheet(f"color: {text_pri}; font-weight: 900;")

        hdr.addWidget(icon_lbl)
        hdr.addWidget(title)
        hdr.addStretch()
        layout.addLayout(hdr)

        # Info message
        desc = QLabel(
            "Oda veya switch değiştirirken fişi çekmeden önce cihazı buradan kapatın.\n"
            "Disk önbelleği (ext4 sync) yazılarak microSD kart bozulması önlenir."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {text_sec}; font-size: 11px;")
        layout.addWidget(desc)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #f59e0b; font-family: monospace; font-size: 11px; font-weight: bold;")
        layout.addWidget(self.status_lbl)

        layout.addStretch()

        # Action Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_cancel = QPushButton("Vazgeç")
        self.btn_cancel.setFixedHeight(42)
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: {'#1e293b' if is_dark else '#cbd5e1'};
                color: {text_pri};
                border: 1px solid {'#334155' if is_dark else '#94a3b8'};
                border-radius: 8px;
                font-weight: 800;
                font-size: 12px;
            }}
        """)
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_reboot = QPushButton("🔄 Yeniden Başlat")
        self.btn_reboot.setFixedHeight(42)
        self.btn_reboot.setCursor(Qt.PointingHandCursor)
        self.btn_reboot.setStyleSheet("""
            QPushButton {
                background-color: #d97706;
                color: #ffffff;
                border: 1px solid #f59e0b;
                border-radius: 8px;
                font-weight: 800;
                font-size: 12px;
            }
            QPushButton:pressed {
                background-color: #b45309;
            }
        """)
        self.btn_reboot.clicked.connect(self._on_reboot)

        self.btn_poweroff = QPushButton("⏻ Güvenli Kapat")
        self.btn_poweroff.setFixedHeight(42)
        self.btn_poweroff.setCursor(Qt.PointingHandCursor)
        self.btn_poweroff.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: #ffffff;
                border: 1px solid #ef4444;
                border-radius: 8px;
                font-weight: 900;
                font-size: 12px;
            }
            QPushButton:pressed {
                background-color: #991b1b;
            }
        """)
        self.btn_poweroff.clicked.connect(self._on_poweroff)

        btn_row.addWidget(self.btn_cancel, 1)
        btn_row.addWidget(self.btn_reboot, 1)
        btn_row.addWidget(self.btn_poweroff, 1)
        layout.addLayout(btn_row)

    def _execute_power_action(self, action: str):
        """Flush filesystem buffers (sync) and trigger systemd poweroff/reboot safely."""
        try:
            os.sync()
        except Exception:
            pass

        cmds = (
            [
                ["sudo", "-n", "systemctl", "poweroff"],
                ["sudo", "-n", "/sbin/poweroff"],
                ["systemctl", "poweroff"],
            ]
            if action == "poweroff"
            else [
                ["sudo", "-n", "systemctl", "reboot"],
                ["sudo", "-n", "/sbin/reboot"],
                ["systemctl", "reboot"],
            ]
        )
        for cmd in cmds:
            try:
                res = subprocess.run(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=3.0,
                    shell=False,
                )
                if res.returncode == 0:
                    return True
            except Exception:
                continue
        return False

    def _on_poweroff(self):
        self.status_lbl.setText("Disk önbelleği yazılıyor (sync)... Cihaz kapatılıyor, lütfen bekleyin.")
        self.btn_poweroff.setEnabled(False)
        self.btn_reboot.setEnabled(False)
        QTimer.singleShot(150, lambda: self._execute_power_action("poweroff"))

    def _on_reboot(self):
        self.status_lbl.setText("Disk önbelleği yazılıyor (sync)... Cihaz yeniden başlatılıyor.")
        self.btn_poweroff.setEnabled(False)
        self.btn_reboot.setEnabled(False)
        QTimer.singleShot(150, lambda: self._execute_power_action("reboot"))


class TopBar(QFrame):
    """Fixed 40px top status bar with vector indicators, real network telemetry, and safe shutdown button."""

    theme_toggled = Signal(str)

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("TopBar")
        self.setFixedHeight(config.TOP_BAR_HEIGHT)
        self._eth_connected = False
        self._eth_speed = 0
        self._wifi_connected = False
        self._init_ui()
        self.update_theme()

        # 1-second clock timer
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)
        self._update_clock()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(8)

        # ==========================================
        # 1. Left Section: Logo, Title, Profile
        # ==========================================
        left_box = QHBoxLayout()
        left_box.setContentsMargins(0, 0, 0, 0)
        left_box.setSpacing(7)

        # Official Logo (26x26 smoothly scaled)
        self.logo_label = QLabel()
        self.logo_label.setFixedSize(26, 26)
        self.logo_label.setStyleSheet("background: transparent;")
        self.update_logo()

        # Title: Ç.I.R.A.K.
        self.title_label = QLabel("Ç.I.R.A.K.")
        title_font = QFont("DejaVu Sans Mono", 11, QFont.ExtraBold)
        self.title_label.setFont(title_font)

        # Divider
        self.divider_label = QLabel("|")

        # Profile
        self.profile_lbl = QLabel("Profil:")
        self.profile_val = QLabel(config.DEFAULT_PROFILE)
        prof_font = QFont("DejaVu Sans Mono", 9, QFont.Bold)
        self.profile_val.setFont(prof_font)

        left_box.addWidget(self.logo_label)
        left_box.addWidget(self.title_label)
        left_box.addWidget(self.divider_label)
        left_box.addWidget(self.profile_lbl)
        left_box.addWidget(self.profile_val)

        layout.addLayout(left_box)
        layout.addStretch()

        # ==========================================
        # 2. Right Section: Ethernet, Wi-Fi, Power Volt, Clock, Safe Shutdown Button
        # ==========================================
        right_box = QHBoxLayout()
        right_box.setContentsMargins(0, 0, 0, 0)
        right_box.setSpacing(10)

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

        # Wi-Fi Status & Connection Button (Touchable vector SVG icon + label)
        self.wifi_btn = QPushButton(" Wi-Fi")
        self.wifi_btn.setFixedHeight(26)
        self.wifi_btn.setCursor(Qt.PointingHandCursor)
        self.wifi_btn.setToolTip("Kablosuz Ağa Bağlan (eduroam 802.1X / WPA2)")
        self.wifi_btn.setIconSize(QSize(15, 15))
        self.wifi_btn.clicked.connect(self._open_wifi_connect_dialog)

        # Power Status (Lightning SVG + voltage text)
        self.power_box = QHBoxLayout()
        self.power_box.setContentsMargins(0, 0, 0, 0)
        self.power_box.setSpacing(3)

        self.power_icon = QLabel()
        self.power_icon.setFixedSize(14, 14)
        self.power_icon.setStyleSheet("background: transparent;")
        self.power_icon.setPixmap(get_svg_pixmap("power_bolt", color="#f59e0b", size=14))

        self.power_val = QLabel("5.1V")
        pwr_font = QFont("DejaVu Sans Mono", 9, QFont.Bold)
        self.power_val.setFont(pwr_font)

        self.power_box.addWidget(self.power_icon)
        self.power_box.addWidget(self.power_val)

        # Live Digital Monospace Clock
        self.clock_label = QLabel("00:00:00")
        clock_font = QFont("DejaVu Sans Mono", 10, QFont.Bold)
        self.clock_label.setFont(clock_font)

        # Safe Shutdown / Reboot Button (Tactile Red Button)
        self.power_btn = QPushButton(" Kapat")
        self.power_btn.setFixedHeight(26)
        self.power_btn.setCursor(Qt.PointingHandCursor)
        self.power_btn.setToolTip("Cihazı Güvenli Kapat / Yeniden Başlat")
        self.power_btn.setIcon(QIcon(get_svg_pixmap("power_off", color="#ffffff", size=14)))
        self.power_btn.setIconSize(QSize(14, 14))
        self.power_btn.clicked.connect(self._open_power_dialog)

        right_box.addLayout(self.eth_box)
        right_box.addWidget(self.wifi_btn)
        right_box.addLayout(self.power_box)
        right_box.addWidget(self.clock_label)
        right_box.addWidget(self.power_btn)

        layout.addLayout(right_box)

        # Set initial network telemetry
        self.update_eth_status(connected=False, speed_mbps=0)
        self.update_wifi_status(connected=False)

    def _open_wifi_connect_dialog(self):
        from cirak.gui.dialogs.wifi_connect_dialog import WiFiConnectDialog
        dlg = WiFiConnectDialog(parent=self.window())
        dlg.connection_changed.connect(lambda: self.update_wifi_status(True))
        dlg.exec()

    def _open_power_dialog(self):
        dlg = PowerDialog(self.window())
        dlg.exec()

    def update_logo(self):
        """Update logo based on active theme: dark logo on dark theme, light logo on light theme."""
        is_dark = ThemeManager.get_current_theme() == config.THEME_DARK
        logo_path = config.LOGO_DARK_PATH if is_dark else config.LOGO_LIGHT_PATH
        if not logo_path.exists():
            logo_path = config.LOGO_PATH

        if logo_path.exists():
            pix = QPixmap(str(logo_path))
            scaled_pix = pix.scaled(26, 26, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.logo_label.setPixmap(scaled_pix)

    def update_theme(self):
        """Refresh top bar colors and logo to match active theme (Dark or Light)."""
        is_dark = ThemeManager.get_current_theme() == config.THEME_DARK
        colors = ThemeManager.get_colors()
        self.update_logo()

        title_color = "#22d3ee" if is_dark else "#0369a1"
        div_color = "#334155" if is_dark else "#64748b"
        prof_lbl_color = "#64748b" if is_dark else "#334155"
        prof_val_color = "#f59e0b" if is_dark else "#b45309"
        pwr_color = "#10b981" if is_dark else "#047857"

        self.title_label.setStyleSheet(f"background: transparent; color: {title_color}; font-weight: 900;")
        self.divider_label.setStyleSheet(f"background: transparent; color: {div_color}; font-weight: bold;")
        self.profile_lbl.setStyleSheet(f"background: transparent; color: {prof_lbl_color}; font-size: 11px;")
        self.profile_val.setStyleSheet(f"background: transparent; color: {prof_val_color}; font-weight: 700;")
        self.power_val.setStyleSheet(f"background: transparent; color: {pwr_color}; font-weight: 700;")
        self.clock_label.setStyleSheet(f"background: transparent; color: {colors['text_primary']}; font-weight: 700;")

        self.power_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: #ffffff;
                border: 1px solid #ef4444;
                border-radius: 5px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 800;
            }
            QPushButton:hover {
                background-color: #ef4444;
            }
            QPushButton:pressed {
                background-color: #991b1b;
            }
        """)

        self.update_eth_status(self._eth_connected, self._eth_speed)
        self.update_wifi_status(self._wifi_connected)

    def update_eth_status(self, connected: bool, speed_mbps: int = 1000):
        """Update 3-node ethernet port vector icon and speed text."""
        self._eth_connected = connected
        self._eth_speed = speed_mbps
        is_dark = ThemeManager.get_current_theme() == config.THEME_DARK

        if connected:
            color = "#10b981" if is_dark else "#047857"
        else:
            color = "#ef4444" if is_dark else "#b91c1c"
        text = f"eth0 {speed_mbps}M" if (connected and speed_mbps > 0) else ("eth0 UP" if connected else "eth0 Link Yok")

        pix = get_svg_pixmap("ethernet_port", color=color, size=18)
        self.eth_icon_label.setPixmap(pix)
        self.eth_text_label.setText(text)
        self.eth_text_label.setStyleSheet(f"background: transparent; color: {color}; font-weight: 700;")

    def update_wifi_status(self, connected: bool = True):
        """Update touchable Wi-Fi vector button in TopBar."""
        self._wifi_connected = connected
        is_dark = ThemeManager.get_current_theme() == config.THEME_DARK
        fg = ("#22d3ee" if is_dark else "#0369a1") if connected else ("#94a3b8" if is_dark else "#475569")
        bg = ("#083344" if is_dark else "#e0f2fe") if connected else ("#1e293b" if is_dark else "#cbd5e1")
        border = fg if connected else ("#334155" if is_dark else "#94a3b8")
        pix = get_svg_pixmap("wifi", color=fg, size=15)
        self.wifi_btn.setIcon(QIcon(pix))
        self.wifi_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 5px;
                padding: 2px 7px;
                font-family: "DejaVu Sans Mono", monospace;
                font-size: 10px;
                font-weight: 800;
            }}
            QPushButton:pressed {{
                background-color: {fg};
                color: #ffffff;
            }}
        """)

    def update_theme_icon(self):
        """Compatibility alias."""
        self.update_theme()

    def _update_clock(self):
        now = datetime.now().strftime("%H:%M:%S")
        self.clock_label.setText(now)

    def set_profile_name(self, name: str):
        self.profile_val.setText(name)
