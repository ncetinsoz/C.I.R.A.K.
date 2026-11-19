"""
Settings & Profile View for Ç.I.R.A.K. (LinkRunner AT 2000 Grade).
Provides touch-optimized configuration for:
  1. IP Configuration: Automatic (DHCP) or Static IPv4 (IP, CIDR Prefix, Gateway, DNS)
  2. Layer 2 Override: IEEE 802.1Q VLAN ID Tagging & Custom MAC Address Spoofing/Cloning
  3. Date/Time & NTP Synchronization (Default: time.deu.edu.tr)
  4. Display Theme: Dark Mode (Default) / Soft Industrial Light Mode
  5. System Specifications Popup Modal (Hardware & Software telemetry at a glance)
Includes direct tap-to-open Touch Keyboard/Keypad on all inputs, large tactile VLAN/MAC toggle buttons,
and full Dark/Light theme consistency.
"""

import os
import platform
import shutil
from datetime import datetime
from typing import Optional, Dict
from PySide6.QtCore import Qt, Signal, QTimer, QThreadPool
from PySide6.QtGui import QFont, QMouseEvent
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QFrame,
    QLineEdit,
    QDialog,
)
import cirak
from cirak import config
from cirak.backend.network_detector import NetworkDetector
from cirak.backend.settings_manager import SettingsManager
from cirak.core.worker import BaseWorker
from cirak.gui.theme import ThemeManager


class TouchableLineEdit(QLineEdit):
    """
    Touch-optimized QLineEdit for 7-inch linuxfb screens.
    Emits `tapped` immediately when touched so the on-screen touch keypad/keyboard opens
    even without a physical USB keyboard or hitting a separate side button.
    """

    tapped = Signal()

    def __init__(self, text: str = "", parent: QWidget = None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self._visually_active = True

    def set_visually_active(self, active: bool):
        """Track visual active/inactive state while keeping widget touch-receptive."""
        self._visually_active = active
        self.setProperty("activeInput", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event: QMouseEvent):
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            self.tapped.emit()


class TactileToggleButton(QPushButton):
    """
    Large, finger-friendly checkable toggle button replacing tiny QCheckBox indicators
    for VLAN 802.1Q and Custom MAC activation on 7-inch touchscreens.
    Provides QCheckBox-compatible `.isChecked()`, `.setChecked()`, and `.toggled` signal.
    """

    def __init__(self, label_off: str, label_on: str, parent: QWidget = None):
        super().__init__(parent)
        self._label_off = label_off
        self._label_on = label_on
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(27)
        self.setMinimumWidth(148)
        self.toggled.connect(self._refresh_appearance)
        self._refresh_appearance(False)

    def _refresh_appearance(self, checked: bool):
        colors = ThemeManager.get_colors()
        is_dark = ThemeManager.get_current_theme() == config.THEME_DARK
        if checked:
            self.setText(f"☑ {self._label_on}")
            bg = "#059669" if is_dark else "#10b981"
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg};
                    color: #ffffff;
                    border: 1.5px solid #34d399;
                    border-radius: 6px;
                    padding: 2px 8px;
                    font-size: 10px;
                    font-weight: 900;
                    text-align: left;
                }}
            """)
        else:
            self.setText(f"☐ {self._label_off}")
            bg = "#0f172a" if is_dark else "#e2e8f0"
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg};
                    color: {colors['text_secondary']};
                    border: 1.5px solid {colors['card_border']};
                    border-radius: 6px;
                    padding: 2px 8px;
                    font-size: 10px;
                    font-weight: 700;
                    text-align: left;
                }}
            """)


class TouchKeypadDialog(QDialog):
    """On-screen touch keypad & full QWERTY keyboard for entering IP, CIDR, VLAN, MAC, Hostname, Email, Password, or SNMP Community."""

    def __init__(self, title: str, initial_value: str, mode: str = "ip", parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.mode = mode  # "ip", "vlan", "mac", "host", "email", "password", "snmp"
        self._upper = False
        self._alpha_buttons = []
        if mode in ("host", "email", "password", "snmp"):
            self.setFixedSize(740, 405)
        elif mode == "mac":
            self.setFixedSize(560, 350)
        else:
            self.setFixedSize(500, 340)
        self.setModal(True)
        self.result_text = initial_value
        self._init_ui(title, initial_value)

    def _init_ui(self, title: str, initial_value: str):
        colors = ThemeManager.get_colors()
        is_dark = ThemeManager.get_current_theme() == config.THEME_DARK
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg_main']};
                border: 2px solid {colors['accent_cyan']};
                border-radius: 12px;
            }}
            QLabel {{
                background: transparent;
                color: {colors['accent_cyan']};
                font-weight: 800;
            }}
            QLineEdit {{
                background-color: {colors['card_bg']};
                color: {colors['text_primary']};
                border: 1.5px solid {colors['accent_cyan']};
                border-radius: 6px;
                padding: 4px 10px;
                font-family: "DejaVu Sans Mono", monospace;
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton {{
                background-color: {'#1e293b' if is_dark else '#f8fafc'};
                color: {colors['text_primary']};
                border: 1px solid {colors['card_border']};
                border-radius: 6px;
                font-family: "DejaVu Sans Mono", monospace;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:pressed {{
                background-color: {colors['accent_cyan']};
                color: #ffffff;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        hdr_row = QHBoxLayout()
        lbl_title = QLabel(f"⌨ {title}")
        lbl_title.setFont(QFont("DejaVu Sans", 11, QFont.Bold))
        hdr_row.addWidget(lbl_title)
        hdr_row.addStretch()
        layout.addLayout(hdr_row)

        self.input_edit = QLineEdit(initial_value)
        self.input_edit.setFixedHeight(36)
        layout.addWidget(self.input_edit)

        if self.mode in ("host", "email", "password", "snmp"):
            preset_row = QHBoxLayout()
            preset_row.setSpacing(6)
            if self.mode == "email":
                presets = ("@deu.edu.tr", "@ogr.deu.edu.tr", "eduroam", ".edu.tr")
            elif self.mode == "snmp":
                presets = ("public", "private", "deu-snmp", "campus-ro")
            elif self.mode == "password":
                presets = ("@", "!", "#", "$", "%", "&", "*", "?")
            else:
                presets = ("time.deu.edu.tr", "pool.ntp.org", "tr.pool.ntp.org", ".edu.tr", ".com")

            for preset in presets:
                p_btn = QPushButton(preset)
                p_btn.setFixedHeight(28)
                p_btn.setStyleSheet(
                    f"font-size: 10px; color: {colors['accent_cyan']}; border: 1px solid {colors['accent_cyan']};"
                )
                p_btn.clicked.connect(lambda checked=False, val=preset: self._on_preset(val))
                preset_row.addWidget(p_btn)
            layout.addLayout(preset_row)

            # Full QWERTY + Numbers + Shift
            rows = [
                ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "_", "⌫"],
                ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p", "@", "Temizle"],
                ["a", "s", "d", "f", "g", "h", "j", "k", "l", ".", ":", "/", "!"],
                ["⇧ HARF", "z", "x", "c", "v", "b", "n", "m", "#", "+", "="],
            ]
            for r_keys in rows:
                r_layout = QHBoxLayout()
                r_layout.setSpacing(4)
                for k in r_keys:
                    btn = QPushButton(k)
                    btn.setFixedHeight(38)
                    if k == "⇧ HARF":
                        btn.clicked.connect(self._toggle_shift)
                        self._shift_btn = btn
                    else:
                        if len(k) == 1 and k.isalpha():
                            self._alpha_buttons.append(btn)
                        btn.clicked.connect(lambda checked=False, b=btn: self._on_key(b.text()))
                    r_layout.addWidget(btn)
                layout.addLayout(r_layout)
        else:
            grid = QGridLayout()
            grid.setSpacing(6)
            if self.mode == "mac":
                keys = [
                    "1", "2", "3", "A", "B",
                    "4", "5", "6", "C", "D",
                    "7", "8", "9", "E", "F",
                    ":", "0", "-", "⌫", "Temizle",
                ]
                cols = 5
            elif self.mode == "vlan":
                keys = [
                    "1", "2", "3", "⌫",
                    "4", "5", "6", "Temizle",
                    "7", "8", "9", "10",
                    "0", "24", "100", "200",
                ]
                cols = 4
            else:
                keys = [
                    "1", "2", "3", "⌫",
                    "4", "5", "6", "Temizle",
                    "7", "8", "9", ".",
                    "0", "192.", "168.", "10.",
                ]
                cols = 4

            for idx, k in enumerate(keys):
                btn = QPushButton(k)
                btn.setFixedHeight(42)
                btn.clicked.connect(lambda checked=False, key=k: self._on_key(key))
                grid.addWidget(btn, idx // cols, idx % cols)
            layout.addLayout(grid)

        bottom = QHBoxLayout()
        bottom.setSpacing(10)
        btn_cancel = QPushButton("✕ İptal")
        btn_cancel.setFixedHeight(36)
        btn_cancel.clicked.connect(self.reject)

        btn_ok = QPushButton("✓ Tamam (Onayla)")
        btn_ok.setFixedHeight(36)
        btn_ok.setStyleSheet(
            "background-color: #059669; color: #ffffff; border: 1.5px solid #10b981; font-size: 13px; font-weight: 900;"
        )
        btn_ok.clicked.connect(self._on_accept)

        bottom.addWidget(btn_cancel, 1)
        bottom.addWidget(btn_ok, 2)
        layout.addLayout(bottom)

    def _toggle_shift(self):
        self._upper = not self._upper
        for b in self._alpha_buttons:
            b.setText(b.text().upper() if self._upper else b.text().lower())

    def _on_preset(self, val: str):
        if val.startswith((".", "@")) or len(val) == 1:
            self.input_edit.setText(self.input_edit.text() + val)
        else:
            self.input_edit.setText(val)

    def _on_key(self, key: str):
        cur = self.input_edit.text()
        if key == "⌫":
            self.input_edit.setText(cur[:-1])
        elif key == "Temizle":
            self.input_edit.clear()
        elif self.mode == "vlan" and key in ("10", "24", "100", "200") and not cur:
            self.input_edit.setText(key)
        else:
            self.input_edit.setText(cur + key.lower() if self.mode == "mac" else cur + key)

    def _on_accept(self):
        self.result_text = self.input_edit.text().strip() if self.mode != "password" else self.input_edit.text()
        self.accept()


class SystemInfoDialog(QDialog):
    """
    Concise ('hap gibi') Hardware & Software System Properties Popup Modal.
    Reads live kernel/sysfs/procfs telemetry without external heavy dependencies.
    """

    def __init__(self, manager: SettingsManager, parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle("Ç.I.R.A.K. Sistem Özellikleri")
        self.setFixedSize(680, 390)
        self.setModal(True)
        self.manager = manager
        self._init_ui()

    @staticmethod
    def collect_system_specs(manager: Optional[SettingsManager] = None) -> Dict[str, str]:
        """Collect concise hardware, OS, thermal, memory, storage, and NIC specs."""
        specs: Dict[str, str] = {}

        # 1. Software & Framework Version
        py_ver = platform.python_version()
        specs["sw_version"] = f"Ç.I.R.A.K. v{getattr(cirak, '__version__', '0.3.2')} (Python {py_ver} / PySide6 Qt6)"

        # 2. Hardware / Board Model
        hw_model = ""
        try:
            if os.path.exists("/proc/device-tree/model"):
                with open("/proc/device-tree/model", "rb") as f:
                    hw_model = f.read().decode("utf-8", errors="ignore").strip("\x00").strip()
        except Exception:
            pass
        if not hw_model:
            hw_model = f"Linux El Terminali ({platform.machine()})"
        specs["hw_model"] = hw_model

        # 3. CPU & Thermal Sensor
        cpu_cores = os.cpu_count() or 4
        cpu_temp = ""
        try:
            if os.path.exists("/sys/class/thermal/thermal_zone0/temp"):
                with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                    milli = int(f.read().strip())
                    cpu_temp = f"{milli / 1000.0:.1f} °C"
        except Exception:
            pass
        specs["cpu_info"] = f"{cpu_cores} Çekirdek ({platform.machine()})" + (f" | Sıcaklık: {cpu_temp}" if cpu_temp else "")

        # 4. RAM Usage (/proc/meminfo)
        ram_str = "Bilinmiyor"
        try:
            mem_total_kb = 0
            mem_avail_kb = 0
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        mem_total_kb = int(line.split()[1])
                    elif line.startswith("MemAvailable:"):
                        mem_avail_kb = int(line.split()[1])
            if mem_total_kb > 0:
                used_mb = (mem_total_kb - mem_avail_kb) // 1024
                total_mb = mem_total_kb // 1024
                pct = ((mem_total_kb - mem_avail_kb) / float(mem_total_kb)) * 100.0
                ram_str = f"{used_mb} MB / {total_mb} MB (%{pct:.0f} Kullanımda)"
        except Exception:
            pass
        specs["ram_info"] = ram_str

        # 5. Storage / microSD Usage
        disk_str = "Bilinmiyor"
        try:
            du = shutil.disk_usage("/")
            used_gb = du.used / (1024 ** 3)
            total_gb = du.total / (1024 ** 3)
            pct = (du.used / float(du.total)) * 100.0 if du.total else 0.0
            disk_str = f"{used_gb:.1f} GB / {total_gb:.1f} GB Dolu (%{pct:.0f})"
        except Exception:
            pass
        specs["disk_info"] = disk_str

        # 6. OS & Kernel
        os_name = ""
        try:
            if os.path.exists("/etc/os-release"):
                with open("/etc/os-release", "r") as f:
                    for line in f:
                        if line.startswith("PRETTY_NAME="):
                            os_name = line.split("=", 1)[1].strip().strip('"')
                            break
        except Exception:
            pass
        kernel_ver = platform.release()
        specs["os_kernel"] = f"{os_name or 'Linux'} | Kernel: {kernel_ver}"

        # 7. System Uptime
        uptime_str = "--"
        try:
            if os.path.exists("/proc/uptime"):
                with open("/proc/uptime", "r") as f:
                    up_sec = int(float(f.read().split()[0]))
                    days, rem = divmod(up_sec, 86400)
                    hours, rem = divmod(rem, 3600)
                    mins, _ = divmod(rem, 60)
                    if days > 0:
                        uptime_str = f"{days} gün, {hours} sa, {mins} dk"
                    else:
                        uptime_str = f"{hours} saat, {mins} dakika"
        except Exception:
            pass
        specs["uptime"] = uptime_str

        # 8. Network Interfaces (eth0 & wlan0)
        eth_iface = NetworkDetector.get_active_interface() or "eth0"
        eth_ip = NetworkDetector.get_ip_address_cidr(eth_iface) or "IP Yok"
        eth_mac = NetworkDetector.get_mac_address(eth_iface) or "--"
        eth_spd, eth_dup = NetworkDetector.get_speed_duplex(eth_iface)
        spd_txt = f"{eth_spd}M ({eth_dup})" if eth_spd > 0 else "Link Yok"
        specs["eth_info"] = f"{eth_iface}: {eth_ip} | {spd_txt} | MAC: {eth_mac}"

        wlan_mac = NetworkDetector.get_mac_address("wlan0") or "--"
        wlan_ip = NetworkDetector.get_ip_address_cidr("wlan0") or "Pasif / Tarama Modu"
        specs["wlan_info"] = f"wlan0: {wlan_ip} | MAC: {wlan_mac}"

        return specs

    def _init_ui(self):
        colors = ThemeManager.get_colors()
        is_dark = ThemeManager.get_current_theme() == config.THEME_DARK
        specs = self.collect_system_specs(self.manager)

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg_main']};
                border: 2px solid {colors['accent_indigo']};
                border-radius: 12px;
            }}
            QFrame#SpecCard {{
                background-color: {colors['card_bg']};
                border: 1.5px solid {colors['card_border']};
                border-radius: 10px;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("ℹ️ Ç.I.R.A.K. DONANIM VE YAZILIM SİSTEM ÖZELLİKLERİ")
        title.setStyleSheet(f"color: {colors['accent_cyan']}; font-size: 13px; font-weight: 900;")
        badge = QLabel(f"v{getattr(cirak, '__version__', '0.3.2')}")
        badge.setStyleSheet(f"""
            background-color: {'#1e1b4b' if is_dark else '#e0e7ff'};
            color: {colors['accent_indigo']};
            border: 1px solid {colors['accent_indigo']};
            border-radius: 5px;
            padding: 2px 10px;
            font-family: monospace;
            font-weight: 900;
        """)
        hdr.addWidget(title)
        hdr.addStretch()
        hdr.addWidget(badge)
        layout.addLayout(hdr)

        # Specs Card
        card = QFrame()
        card.setObjectName("SpecCard")
        grid = QGridLayout(card)
        grid.setContentsMargins(14, 10, 14, 10)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(7)

        rows = [
            ("Yazılım Sürümü:", specs["sw_version"], colors["accent_cyan"]),
            ("Donanım / Cihaz:", specs["hw_model"], colors["text_primary"]),
            ("İşlemci & Sıcaklık:", specs["cpu_info"], colors["status_success"]),
            ("RAM Bellek:", specs["ram_info"], colors["text_primary"]),
            ("Depolama (Disk):", specs["disk_info"], colors["text_primary"]),
            ("İşletim Sistemi:", specs["os_kernel"], colors["text_secondary"]),
            ("Çalışma Süresi:", specs["uptime"], colors["accent_amber"]),
            ("Kablolu Ağ (LAN):", specs["eth_info"], colors["status_success"]),
            ("Kablosuz (Wi-Fi):", specs["wlan_info"], colors["accent_indigo"]),
        ]

        for idx, (k_txt, v_txt, v_col) in enumerate(rows):
            k_lbl = QLabel(k_txt)
            k_lbl.setStyleSheet(f"color: {colors['text_muted']}; font-size: 11px; font-weight: 800;")
            v_lbl = QLabel(v_txt)
            v_lbl.setStyleSheet(
                f"color: {v_col}; font-family: 'DejaVu Sans Mono', monospace; font-size: 11px; font-weight: 800;"
            )
            grid.addWidget(k_lbl, idx, 0)
            grid.addWidget(v_lbl, idx, 1)

        grid.setColumnStretch(1, 1)
        layout.addWidget(card, 1)

        # Close button
        btn_close = QPushButton("✓ Kapat")
        btn_close.setFixedHeight(34)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {colors['accent_indigo']};
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 900;
            }}
        """)
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)


class SettingsView(QWidget):
    """LinkRunner AT 2000 style Settings view for 800x480 touchscreen."""

    back_requested = Signal()
    theme_changed = Signal(str)
    profile_updated = Signal(str)

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.manager = SettingsManager(simulate=False)
        self._active_worker: Optional[BaseWorker] = None
        self._init_ui()
        self._load_values_into_ui()
        self.update_theme()

        # Live clock updater for NTP panel
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_time_label)
        self.clock_timer.start(1000)
        self._update_time_label()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 6, 12, 6)
        main_layout.setSpacing(6)

        # 1. Header Toolbar
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)

        self.back_btn = QPushButton("← Geri")
        self.back_btn.setFixedSize(68, 28)
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.clicked.connect(self.back_requested.emit)

        self.title_lbl = QLabel("Ağ, VLAN/MAC & Sistem Ayarları")
        title_font = QFont("DejaVu Sans", 11, QFont.Bold)
        self.title_lbl.setFont(title_font)

        self.status_badge = QLabel("HAZIR")
        self.status_badge.setFont(QFont("DejaVu Sans Mono", 8, QFont.Bold))

        self.btn_wifi_connect = QPushButton("📶 Wi-Fi Bağlan")
        self.btn_wifi_connect.setFixedHeight(28)
        self.btn_wifi_connect.setCursor(Qt.PointingHandCursor)
        self.btn_wifi_connect.clicked.connect(self._open_wifi_connect_dialog)

        self.btn_sys_info = QPushButton("ℹ️ Sistem Özellikleri")
        self.btn_sys_info.setFixedHeight(28)
        self.btn_sys_info.setCursor(Qt.PointingHandCursor)
        self.btn_sys_info.clicked.connect(self._open_system_info_dialog)

        self.save_apply_btn = QPushButton("✓ Ağ Ayarlarını Uygula")
        self.save_apply_btn.setProperty("class", "PrimaryBtn")
        self.save_apply_btn.setFixedHeight(28)
        self.save_apply_btn.setCursor(Qt.PointingHandCursor)
        self.save_apply_btn.clicked.connect(self._on_apply_network_clicked)

        header.addWidget(self.back_btn)
        header.addWidget(self.title_lbl)
        header.addStretch()
        header.addWidget(self.status_badge)
        header.addWidget(self.btn_wifi_connect)
        header.addWidget(self.btn_sys_info)
        header.addWidget(self.save_apply_btn)

        # 2. 2-Column Main Settings Layout
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(10)

        # LEFT CARD: IPv4 Configuration (DHCP vs Static)
        self.card_ip = QFrame()
        self.card_ip.setObjectName("SettingsCard")
        l_ip = QVBoxLayout(self.card_ip)
        l_ip.setContentsMargins(10, 8, 10, 8)
        l_ip.setSpacing(6)

        self.lbl_ip_hdr = QLabel("🌐 1. IP ADRES YAPILANDIRMASI (eth0)")
        l_ip.addWidget(self.lbl_ip_hdr)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)
        self.btn_mode_dhcp = QPushButton("Otomatik (DHCP)")
        self.btn_mode_dhcp.setFixedHeight(28)
        self.btn_mode_dhcp.setCursor(Qt.PointingHandCursor)
        self.btn_mode_dhcp.clicked.connect(lambda: self._set_ip_mode("dhcp"))

        self.btn_mode_static = QPushButton("Statik IP")
        self.btn_mode_static.setFixedHeight(28)
        self.btn_mode_static.setCursor(Qt.PointingHandCursor)
        self.btn_mode_static.clicked.connect(lambda: self._set_ip_mode("static"))

        mode_row.addWidget(self.btn_mode_dhcp)
        mode_row.addWidget(self.btn_mode_static)
        l_ip.addLayout(mode_row)

        ip_grid = QGridLayout()
        ip_grid.setHorizontalSpacing(6)
        ip_grid.setVerticalSpacing(5)

        self.lbl_s_ip = QLabel("IP Adresi:")
        self.edit_ip = TouchableLineEdit()
        self.edit_ip.setFixedHeight(26)
        btn_k_ip = self._bind_touch_input(
            "Statik IP Adresi", self.edit_ip, "ip", on_before_open=lambda: self._set_ip_mode("static")
        )

        self.lbl_s_pfx = QLabel("Maske (/CIDR):")
        self.edit_prefix = TouchableLineEdit()
        self.edit_prefix.setFixedHeight(26)
        btn_k_pfx = self._bind_touch_input(
            "Alt Ağ CIDR (Örn: 24)", self.edit_prefix, "vlan", on_before_open=lambda: self._set_ip_mode("static")
        )

        self.lbl_s_gw = QLabel("Ağ Geçidi:")
        self.edit_gw = TouchableLineEdit()
        self.edit_gw.setFixedHeight(26)
        btn_k_gw = self._bind_touch_input(
            "Ağ Geçidi (Gateway) IP", self.edit_gw, "ip", on_before_open=lambda: self._set_ip_mode("static")
        )

        self.lbl_s_dns = QLabel("DNS Sunucu:")
        self.edit_dns = TouchableLineEdit()
        self.edit_dns.setFixedHeight(26)
        btn_k_dns = self._bind_touch_input(
            "Birincil DNS IP", self.edit_dns, "ip", on_before_open=lambda: self._set_ip_mode("static")
        )

        ip_grid.addWidget(self.lbl_s_ip, 0, 0)
        ip_grid.addWidget(self.edit_ip, 0, 1)
        ip_grid.addWidget(btn_k_ip, 0, 2)

        ip_grid.addWidget(self.lbl_s_pfx, 1, 0)
        ip_grid.addWidget(self.edit_prefix, 1, 1)
        ip_grid.addWidget(btn_k_pfx, 1, 2)

        ip_grid.addWidget(self.lbl_s_gw, 2, 0)
        ip_grid.addWidget(self.edit_gw, 2, 1)
        ip_grid.addWidget(btn_k_gw, 2, 2)

        ip_grid.addWidget(self.lbl_s_dns, 3, 0)
        ip_grid.addWidget(self.edit_dns, 3, 1)
        ip_grid.addWidget(btn_k_dns, 3, 2)

        l_ip.addLayout(ip_grid)
        l_ip.addStretch()

        self.div_left = QFrame()
        self.div_left.setFrameShape(QFrame.HLine)
        l_ip.addWidget(self.div_left)

        self.lbl_theme_hdr = QLabel("🎨 4. EKRAN GÖRÜNÜM TEMASI")
        l_ip.addWidget(self.lbl_theme_hdr)

        theme_row = QHBoxLayout()
        theme_row.setSpacing(6)
        self.btn_theme_dark = QPushButton("🌙 Karanlık Mod (Önerilen)")
        self.btn_theme_dark.setFixedHeight(26)
        self.btn_theme_dark.clicked.connect(lambda: self._select_theme(config.THEME_DARK))

        self.btn_theme_light = QPushButton("☀ Aydınlık Mod")
        self.btn_theme_light.setFixedHeight(26)
        self.btn_theme_light.clicked.connect(lambda: self._select_theme(config.THEME_LIGHT))

        theme_row.addWidget(self.btn_theme_dark)
        theme_row.addWidget(self.btn_theme_light)
        l_ip.addLayout(theme_row)

        # RIGHT COLUMN: Card 2 (VLAN & MAC) + Card 3 (NTP & Time)
        right_col = QVBoxLayout()
        right_col.setSpacing(8)

        self.card_l2 = QFrame()
        self.card_l2.setObjectName("SettingsCard")
        l_l2 = QVBoxLayout(self.card_l2)
        l_l2.setContentsMargins(10, 8, 10, 8)
        l_l2.setSpacing(5)

        self.lbl_l2_hdr = QLabel("🏷 2. VLAN (802.1Q) & MAC ADRESİ (LinkRunner Modu)")
        l_l2.addWidget(self.lbl_l2_hdr)

        l2_grid = QGridLayout()
        l2_grid.setHorizontalSpacing(6)
        l2_grid.setVerticalSpacing(6)

        # Large Tactile Toggle Buttons instead of tiny QCheckBoxes
        self.chk_vlan = TactileToggleButton("VLAN: Kapalı", "VLAN: AKTİF")
        self.chk_vlan.toggled.connect(self._on_vlan_toggled)
        self.edit_vlan = TouchableLineEdit("100")
        self.edit_vlan.setFixedHeight(27)
        btn_k_vlan = self._bind_touch_input(
            "802.1Q VLAN ID (1-4094)",
            self.edit_vlan,
            "vlan",
            on_before_open=lambda: self.chk_vlan.setChecked(True),
        )

        self.chk_mac = TactileToggleButton("Özel MAC: Kapalı", "Özel MAC: AKTİF")
        self.chk_mac.toggled.connect(self._on_mac_toggled)
        self.edit_mac = TouchableLineEdit()
        self.edit_mac.setFixedHeight(27)
        btn_k_mac = self._bind_touch_input(
            "Özel MAC Adresi (xx:xx:xx:xx:xx:xx)",
            self.edit_mac,
            "mac",
            on_before_open=lambda: self.chk_mac.setChecked(True),
        )

        l2_grid.addWidget(self.chk_vlan, 0, 0)
        l2_grid.addWidget(self.edit_vlan, 0, 1)
        l2_grid.addWidget(btn_k_vlan, 0, 2)

        l2_grid.addWidget(self.chk_mac, 1, 0)
        l2_grid.addWidget(self.edit_mac, 1, 1)
        l2_grid.addWidget(btn_k_mac, 1, 2)

        l_l2.addLayout(l2_grid)

        mac_reset_row = QHBoxLayout()
        hw_mac = self.manager.get_permanent_mac("eth0")
        self.lbl_hw_mac = QLabel(f"Donanım MAC: {hw_mac}")
        btn_reset_mac = QPushButton("Fabrika MAC'ine Dön")
        btn_reset_mac.setFixedHeight(22)
        btn_reset_mac.setStyleSheet("font-size: 9px; padding: 1px 6px;")
        btn_reset_mac.clicked.connect(self._reset_to_factory_mac)
        mac_reset_row.addWidget(self.lbl_hw_mac)
        mac_reset_row.addStretch()
        mac_reset_row.addWidget(btn_reset_mac)
        l_l2.addLayout(mac_reset_row)

        # Card 3: Date, Time & NTP Synchronization
        self.card_ntp = QFrame()
        self.card_ntp.setObjectName("SettingsCard")
        l_ntp = QVBoxLayout(self.card_ntp)
        l_ntp.setContentsMargins(10, 8, 10, 8)
        l_ntp.setSpacing(5)

        self.lbl_ntp_hdr = QLabel("🕒 3. TARİH, SAAT & NTP SENKRONİZASYONU")
        l_ntp.addWidget(self.lbl_ntp_hdr)

        self.lbl_sys_time = QLabel("Sistem Saati: --")
        l_ntp.addWidget(self.lbl_sys_time)

        ntp_row = QHBoxLayout()
        ntp_row.setSpacing(6)
        self.lbl_ntp_srv = QLabel("NTP Sunucu:")
        self.edit_ntp = TouchableLineEdit(config.DEFAULT_NTP_SERVER)
        self.edit_ntp.setFixedHeight(26)
        btn_k_ntp = self._bind_touch_input("NTP Sunucu Adresi", self.edit_ntp, "host")

        ntp_row.addWidget(self.lbl_ntp_srv)
        ntp_row.addWidget(self.edit_ntp, 1)
        ntp_row.addWidget(btn_k_ntp)
        l_ntp.addLayout(ntp_row)

        ntp_btn_row = QHBoxLayout()
        self.lbl_ntp_status = QLabel("Varsayılan: time.deu.edu.tr (UDP 123)")

        self.btn_sync_ntp = QPushButton("🔄 NTP ile Şimdi Eşitle")
        self.btn_sync_ntp.setFixedHeight(25)
        self.btn_sync_ntp.clicked.connect(self._on_sync_ntp_clicked)

        ntp_btn_row.addWidget(self.lbl_ntp_status, 1)
        ntp_btn_row.addWidget(self.btn_sync_ntp)
        l_ntp.addLayout(ntp_btn_row)

        right_col.addWidget(self.card_l2, 1)
        right_col.addWidget(self.card_ntp, 1)

        columns_layout.addWidget(self.card_ip, 1)
        columns_layout.addLayout(right_col, 1)

        main_layout.addLayout(header)
        main_layout.addLayout(columns_layout, 1)

    def update_theme(self):
        """Apply Dark or Light Industrial theme consistently across all Settings cards and inputs."""
        is_dark = ThemeManager.get_current_theme() == config.THEME_DARK
        colors = ThemeManager.get_colors()
        input_bg = "#020617" if is_dark else "#f8fafc"
        inactive_bg = "#0f172a" if is_dark else "#e2e8f0"

        card_qss = f"""
            QFrame#SettingsCard {{
                background-color: {colors['card_bg']};
                border: 1.5px solid {colors['card_border']};
                border-radius: 10px;
            }}
            QFrame#SettingsCard QLabel {{
                background: transparent;
                border: none;
            }}
            QLineEdit {{
                background-color: {input_bg};
                color: {colors['text_primary']};
                border: 1.5px solid {colors['accent_cyan']};
                border-radius: 5px;
                padding: 2px 6px;
                font-family: "DejaVu Sans Mono", monospace;
                font-size: 11px;
                font-weight: bold;
            }}
            QLineEdit[activeInput="false"] {{
                background-color: {inactive_bg};
                color: {colors['text_muted']};
                border: 1px dashed {colors['card_border']};
            }}
        """
        for card in (self.card_ip, self.card_l2, self.card_ntp):
            card.setStyleSheet(card_qss)

        self.title_lbl.setStyleSheet(f"background: transparent; color: {colors['accent_cyan']}; font-weight: 800;")
        self.status_badge.setStyleSheet(f"""
            background-color: transparent;
            color: {colors['text_secondary']};
            border: 1px solid {colors['card_border']};
            border-radius: 4px;
            padding: 2px 6px;
        """)
        self.btn_wifi_connect.setStyleSheet(f"""
            QPushButton {{
                background-color: {'#083344' if is_dark else '#e0f2fe'};
                color: {colors['accent_cyan']};
                border: 1.5px solid {colors['accent_cyan']};
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 10px;
                font-weight: 800;
            }}
        """)
        self.btn_sys_info.setStyleSheet(f"""
            QPushButton {{
                background-color: {'#1e1b4b' if is_dark else '#e0e7ff'};
                color: {colors['accent_indigo']};
                border: 1.5px solid {colors['accent_indigo']};
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 10px;
                font-weight: 800;
            }}
        """)
        self.lbl_ip_hdr.setStyleSheet(f"color: {colors['accent_cyan']}; font-weight: 900; font-size: 11px;")
        self.lbl_l2_hdr.setStyleSheet(f"color: {colors['status_success']}; font-weight: 900; font-size: 11px;")
        self.lbl_ntp_hdr.setStyleSheet(f"color: {colors['accent_amber']}; font-weight: 900; font-size: 11px;")
        self.lbl_theme_hdr.setStyleSheet(f"color: {colors['accent_indigo']}; font-weight: 900; font-size: 11px;")
        self.div_left.setStyleSheet(f"background-color: {colors['card_border']}; max-height: 1px;")

        for lbl in (self.lbl_s_ip, self.lbl_s_pfx, self.lbl_s_gw, self.lbl_s_dns, self.lbl_ntp_srv):
            lbl.setStyleSheet(f"color: {colors['text_secondary']}; font-size: 10px; font-weight: bold;")

        self.lbl_hw_mac.setStyleSheet(f"color: {colors['text_muted']}; font-family: monospace; font-size: 9px;")
        self.lbl_sys_time.setStyleSheet(
            f"color: {colors['text_primary']}; font-family: monospace; font-size: 11px; font-weight: bold;"
        )
        self.lbl_ntp_status.setStyleSheet(f"color: {colors['text_secondary']}; font-size: 9px; font-family: monospace;")
        self.btn_sync_ntp.setStyleSheet("""
            QPushButton {
                background-color: #d97706;
                color: #ffffff;
                border: none;
                border-radius: 5px;
                padding: 2px 8px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f59e0b;
            }
        """)

        self.chk_vlan._refresh_appearance(self.chk_vlan.isChecked())
        self.chk_mac._refresh_appearance(self.chk_mac.isChecked())
        self._set_ip_mode(self.manager.settings.ip_mode)
        self._update_theme_buttons(ThemeManager.get_current_theme())

    def _bind_touch_input(
        self, title: str, line_edit: TouchableLineEdit, mode: str, on_before_open=None
    ) -> QPushButton:
        """Bind both direct touch on the input field AND the side keypad button to open TouchKeypadDialog."""
        def _trigger():
            if callable(on_before_open):
                on_before_open()
            self._open_keypad(title, line_edit, mode)

        line_edit.tapped.connect(_trigger)

        btn = QPushButton("⌨")
        btn.setFixedSize(32, 26)
        btn.setStyleSheet("font-size: 12px; font-weight: bold; padding: 1px 4px;")
        btn.setToolTip(f"{title} (Dokunmatik Klavye)")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(_trigger)
        return btn

    def _open_keypad(self, title: str, line_edit: QLineEdit, mode: str):
        dlg = TouchKeypadDialog(title=title, initial_value=line_edit.text(), mode=mode, parent=self)
        if dlg.exec() == QDialog.Accepted:
            line_edit.setText(dlg.result_text)

    def _open_wifi_connect_dialog(self):
        from cirak.gui.dialogs.wifi_connect_dialog import WiFiConnectDialog
        dlg = WiFiConnectDialog(parent=self.window())
        dlg.exec()

    def _open_system_info_dialog(self):
        dlg = SystemInfoDialog(manager=self.manager, parent=self)
        dlg.exec()

    def _load_values_into_ui(self):
        s = self.manager.settings
        self.edit_ip.setText(s.static_ip)
        self.edit_prefix.setText(str(s.subnet_prefix))
        self.edit_gw.setText(s.gateway)
        self.edit_dns.setText(s.dns_server)

        self.chk_vlan.setChecked(s.vlan_enabled)
        self.edit_vlan.setText(str(s.vlan_id))
        self.edit_vlan.set_visually_active(s.vlan_enabled)

        self.chk_mac.setChecked(s.custom_mac_enabled)
        self.edit_mac.setText(s.custom_mac)
        self.edit_mac.set_visually_active(s.custom_mac_enabled)

        self.edit_ntp.setText(s.ntp_server or config.DEFAULT_NTP_SERVER)
        self.edit_ntp.set_visually_active(True)

        self._set_ip_mode(s.ip_mode)
        self._update_theme_buttons(ThemeManager.get_current_theme())

    def _set_ip_mode(self, mode: str):
        colors = ThemeManager.get_colors()
        self.manager.settings.ip_mode = mode
        is_static = (mode == "static")

        # Keep inputs touch-responsive so tapping them in DHCP mode auto-switches to Static IP and opens keypad!
        for ed in (self.edit_ip, self.edit_prefix, self.edit_gw, self.edit_dns):
            ed.set_visually_active(is_static)

        active_style = f"background-color: {colors['accent_cyan']}; color: #ffffff; border: 1.5px solid {colors['accent_cyan']}; font-weight: 800;"
        inactive_style = f"background-color: {colors['bg_main']}; color: {colors['text_secondary']}; border: 1px solid {colors['card_border']};"

        self.btn_mode_dhcp.setStyleSheet(inactive_style if is_static else active_style)
        self.btn_mode_static.setStyleSheet(active_style if is_static else inactive_style)

    def _on_vlan_toggled(self, checked: bool):
        self.edit_vlan.set_visually_active(checked)

    def _on_mac_toggled(self, checked: bool):
        self.edit_mac.set_visually_active(checked)

    def _reset_to_factory_mac(self):
        perm = self.manager.get_permanent_mac("eth0")
        if perm:
            self.edit_mac.setText(perm)
        self.chk_mac.setChecked(False)

    def _select_theme(self, theme_name: str):
        ThemeManager.set_theme(theme_name)
        self.manager.settings.theme = theme_name
        self.manager.save()
        self._update_theme_buttons(theme_name)
        self.theme_changed.emit(theme_name)

    def _update_theme_buttons(self, theme_name: str):
        colors = ThemeManager.get_colors()
        is_dark = (theme_name == config.THEME_DARK)
        active = f"background-color: {colors['accent_indigo']}; color: #ffffff; border: 1.5px solid {colors['accent_indigo']}; font-weight: 800;"
        inactive = f"background-color: {colors['bg_main']}; color: {colors['text_secondary']}; border: 1px solid {colors['card_border']};"
        self.btn_theme_dark.setStyleSheet(active if is_dark else inactive)
        self.btn_theme_light.setStyleSheet(inactive if is_dark else active)

    def _update_time_label(self):
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.lbl_sys_time.setText(f"Sistem Tarihi / Saati: {now_str}")

    def _on_apply_network_clicked(self):
        s = self.manager.settings
        s.static_ip = self.edit_ip.text().strip()
        pfx_txt = self.edit_prefix.text().strip().lstrip("/")
        s.subnet_prefix = int(pfx_txt) if pfx_txt.isdigit() else -1
        s.gateway = self.edit_gw.text().strip()
        s.dns_server = self.edit_dns.text().strip()

        s.vlan_enabled = self.chk_vlan.isChecked()
        vlan_txt = self.edit_vlan.text().strip()
        s.vlan_id = int(vlan_txt) if vlan_txt.isdigit() else -1

        s.custom_mac_enabled = self.chk_mac.isChecked()
        s.custom_mac = self.edit_mac.text().strip().lower()
        s.ntp_server = self.edit_ntp.text().strip() or config.DEFAULT_NTP_SERVER

        self.save_apply_btn.setEnabled(False)
        self.status_badge.setText("UYGULANIYOR...")

        self._active_worker = BaseWorker(self.manager.apply_network_config, "eth0")
        self._active_worker.signals.result.connect(self._on_apply_finished, Qt.QueuedConnection)
        self._active_worker.signals.error.connect(self._on_apply_error, Qt.QueuedConnection)
        QThreadPool.globalInstance().start(self._active_worker)

    def _on_apply_finished(self, res: tuple):
        is_dark = ThemeManager.get_current_theme() == config.THEME_DARK
        colors = ThemeManager.get_colors()
        self.save_apply_btn.setEnabled(True)
        ok, msg = res
        if ok:
            self.status_badge.setText("✓ KAYDEDİLDİ")
            bg = "#022c22" if is_dark else "#dcfce7"
            fg = colors["status_success"]
            self.profile_updated.emit(self.manager.settings.profile_name)
        else:
            self.status_badge.setText("✗ HATA")
            bg = "#450a0a" if is_dark else "#fee2e2"
            fg = colors["status_error"]

        self.status_badge.setStyleSheet(f"""
            background-color: {bg};
            color: {fg};
            border: 1px solid {fg};
            border-radius: 4px;
            padding: 2px 6px;
        """)
        self.lbl_ntp_status.setText(msg)

    def _on_apply_error(self, err_tuple):
        self.save_apply_btn.setEnabled(True)
        self.status_badge.setText("✗ HATA")

    def _on_sync_ntp_clicked(self):
        srv = self.edit_ntp.text().strip() or config.DEFAULT_NTP_SERVER
        self.btn_sync_ntp.setEnabled(False)
        self.btn_sync_ntp.setText("Eşitleniyor...")
        self.lbl_ntp_status.setText(f"{srv} sorgulanıyor...")

        self._active_worker = BaseWorker(self.manager.sync_ntp_time, srv)
        self._active_worker.signals.result.connect(self._on_ntp_finished, Qt.QueuedConnection)
        self._active_worker.signals.error.connect(self._on_ntp_error, Qt.QueuedConnection)
        QThreadPool.globalInstance().start(self._active_worker)

    def _on_ntp_finished(self, res: tuple):
        colors = ThemeManager.get_colors()
        self.btn_sync_ntp.setEnabled(True)
        self.btn_sync_ntp.setText("🔄 NTP ile Şimdi Eşitle")
        ok, msg = res
        self.lbl_ntp_status.setText(msg)
        self.lbl_ntp_status.setStyleSheet(
            f"color: {colors['status_success'] if ok else colors['status_error']}; font-size: 9px; font-family: monospace; font-weight: bold;"
        )
        self._update_time_label()

    def _on_ntp_error(self, err_tuple):
        self.btn_sync_ntp.setEnabled(True)
        self.btn_sync_ntp.setText("🔄 NTP ile Şimdi Eşitle")
        self.lbl_ntp_status.setText("NTP bağlantı hatası.")
