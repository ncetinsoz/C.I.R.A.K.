"""
Settings & Profile View for Ç.I.R.A.K. (LinkRunner AT 2000 Grade).
Provides touch-optimized configuration for:
  1. IP Configuration: Automatic (DHCP) or Static IPv4 (IP, CIDR Prefix, Gateway, DNS)
  2. Layer 2 Override: IEEE 802.1Q VLAN ID Tagging & Custom MAC Address Spoofing/Cloning
  3. Date/Time & NTP Synchronization (Default: time.deu.edu.tr)
  4. Display Theme: Dark Mode (Default) / Soft Industrial Light Mode
Includes an integrated Touch Keypad Dialog and full Dark/Light theme consistency.
"""

from datetime import datetime
from typing import Optional
from PySide6.QtCore import Qt, Signal, QTimer, QThreadPool
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QFrame,
    QLineEdit,
    QCheckBox,
    QDialog,
)
from cirak import config
from cirak.backend.settings_manager import SettingsManager
from cirak.core.worker import BaseWorker
from cirak.gui.theme import ThemeManager


class TouchKeypadDialog(QDialog):
    """On-screen touch keypad for entering IP, CIDR, VLAN, MAC, or NTP host on 7-inch screen."""

    def __init__(self, title: str, initial_value: str, mode: str = "ip", parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(460, 310)
        self.setModal(True)
        self.mode = mode  # "ip", "vlan", "mac", "host"
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
                border: 1.5px solid {colors['card_border']};
                border-radius: 6px;
                padding: 4px 8px;
                font-family: "DejaVu Sans Mono", monospace;
                font-size: 15px;
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
        layout.setSpacing(8)

        lbl_title = QLabel(f"⌨ {title}")
        layout.addWidget(lbl_title)

        self.input_edit = QLineEdit(initial_value)
        self.input_edit.setFixedHeight(34)
        layout.addWidget(self.input_edit)

        grid = QGridLayout()
        grid.setSpacing(5)

        if self.mode == "mac":
            keys = [
                "1", "2", "3", "A", "B",
                "4", "5", "6", "C", "D",
                "7", "8", "9", "E", "F",
                ":", "0", ".", "⌫", "Temizle",
            ]
            cols = 5
        elif self.mode == "host":
            keys = [
                "1", "2", "3", "time.", "pool.",
                "4", "5", "6", "deu.", "edu.",
                "7", "8", "9", "tr", "org",
                ".", "0", "-", "⌫", "Temizle",
            ]
            cols = 5
        else:
            keys = [
                "1", "2", "3", "⌫",
                "4", "5", "6", "Temizle",
                "7", "8", "9", ".",
                "0", "00", "/", ":",
            ]
            cols = 4

        for idx, k in enumerate(keys):
            btn = QPushButton(k)
            btn.setFixedHeight(36)
            btn.clicked.connect(lambda checked=False, key=k: self._on_key(key))
            grid.addWidget(btn, idx // cols, idx % cols)

        layout.addLayout(grid)

        bottom = QHBoxLayout()
        btn_cancel = QPushButton("İptal")
        btn_cancel.setFixedHeight(34)
        btn_cancel.clicked.connect(self.reject)

        btn_ok = QPushButton("✓ Tamam")
        btn_ok.setFixedHeight(34)
        btn_ok.setStyleSheet("background-color: #059669; color: #ffffff; border: 1px solid #10b981;")
        btn_ok.clicked.connect(self._on_accept)

        bottom.addWidget(btn_cancel)
        bottom.addWidget(btn_ok)
        layout.addLayout(bottom)

    def _on_key(self, key: str):
        cur = self.input_edit.text()
        if key == "⌫":
            self.input_edit.setText(cur[:-1])
        elif key == "Temizle":
            self.input_edit.clear()
        else:
            self.input_edit.setText(cur + key.lower() if self.mode == "mac" else cur + key)

    def _on_accept(self):
        self.result_text = self.input_edit.text().strip()
        self.accept()


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
        header.setSpacing(8)

        self.back_btn = QPushButton("← Geri")
        self.back_btn.setFixedSize(70, 28)
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.clicked.connect(self.back_requested.emit)

        self.title_lbl = QLabel("Sistem, Ağ, VLAN/MAC & NTP Ayarları")
        title_font = QFont("DejaVu Sans", 11, QFont.Bold)
        self.title_lbl.setFont(title_font)

        self.status_badge = QLabel("HAZIR")
        self.status_badge.setFont(QFont("DejaVu Sans Mono", 8, QFont.Bold))

        self.save_apply_btn = QPushButton("✓ Ağ Ayarlarını Uygula")
        self.save_apply_btn.setProperty("class", "PrimaryBtn")
        self.save_apply_btn.setFixedHeight(28)
        self.save_apply_btn.setCursor(Qt.PointingHandCursor)
        self.save_apply_btn.clicked.connect(self._on_apply_network_clicked)

        header.addWidget(self.back_btn)
        header.addWidget(self.title_lbl)
        header.addStretch()
        header.addWidget(self.status_badge)
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
        self.edit_ip = QLineEdit()
        self.edit_ip.setFixedHeight(25)
        btn_k_ip = self._make_keypad_btn("Statik IP Adresi", self.edit_ip, "ip")

        self.lbl_s_pfx = QLabel("Maske (/CIDR):")
        self.edit_prefix = QLineEdit()
        self.edit_prefix.setFixedHeight(25)
        btn_k_pfx = self._make_keypad_btn("Alt Ağ CIDR (Örn: 24)", self.edit_prefix, "vlan")

        self.lbl_s_gw = QLabel("Ağ Geçidi:")
        self.edit_gw = QLineEdit()
        self.edit_gw.setFixedHeight(25)
        btn_k_gw = self._make_keypad_btn("Ağ Geçidi (Gateway) IP", self.edit_gw, "ip")

        self.lbl_s_dns = QLabel("DNS Sunucu:")
        self.edit_dns = QLineEdit()
        self.edit_dns.setFixedHeight(25)
        btn_k_dns = self._make_keypad_btn("Birincil DNS IP", self.edit_dns, "ip")

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
        l2_grid.setVerticalSpacing(5)

        self.chk_vlan = QCheckBox("VLAN Etiketi (ID):")
        self.chk_vlan.toggled.connect(self._on_vlan_toggled)
        self.edit_vlan = QLineEdit("100")
        self.edit_vlan.setFixedHeight(25)
        btn_k_vlan = self._make_keypad_btn("802.1Q VLAN ID (1-4094)", self.edit_vlan, "vlan")

        self.chk_mac = QCheckBox("Özel MAC Adresi:")
        self.chk_mac.toggled.connect(self._on_mac_toggled)
        self.edit_mac = QLineEdit()
        self.edit_mac.setFixedHeight(25)
        btn_k_mac = self._make_keypad_btn("Özel MAC Adresi (xx:xx:xx:xx:xx:xx)", self.edit_mac, "mac")

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
        self.edit_ntp = QLineEdit(config.DEFAULT_NTP_SERVER)
        self.edit_ntp.setFixedHeight(25)
        btn_k_ntp = self._make_keypad_btn("NTP Sunucu Adresi", self.edit_ntp, "host")

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
        disabled_bg = "#0f172a" if is_dark else "#cbd5e1"

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
                border: 1px solid {colors['card_border']};
                border-radius: 5px;
                padding: 2px 6px;
                font-family: "DejaVu Sans Mono", monospace;
                font-size: 11px;
                font-weight: bold;
            }}
            QLineEdit:disabled {{
                background-color: {disabled_bg};
                color: {colors['text_muted']};
                border: 1px solid {colors['card_border']};
            }}
            QCheckBox {{
                color: {colors['text_primary']};
                font-weight: bold;
                font-size: 11px;
                spacing: 6px;
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
            padding: 2px 8px;
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

        self._set_ip_mode(self.manager.settings.ip_mode)
        self._update_theme_buttons(ThemeManager.get_current_theme())

    def _make_keypad_btn(self, title: str, line_edit: QLineEdit, mode: str) -> QPushButton:
        btn = QPushButton("Gir")
        btn.setFixedSize(36, 25)
        btn.setStyleSheet("font-size: 10px; font-weight: bold; padding: 1px 4px;")
        btn.setToolTip(f"{title} (Dokunmatik Tuş Takımı)")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda: self._open_keypad(title, line_edit, mode))
        return btn

    def _open_keypad(self, title: str, line_edit: QLineEdit, mode: str):
        if not line_edit.isEnabled():
            return
        dlg = TouchKeypadDialog(title=title, initial_value=line_edit.text(), mode=mode, parent=self)
        if dlg.exec() == QDialog.Accepted:
            line_edit.setText(dlg.result_text)

    def _load_values_into_ui(self):
        s = self.manager.settings
        self.edit_ip.setText(s.static_ip)
        self.edit_prefix.setText(str(s.subnet_prefix))
        self.edit_gw.setText(s.gateway)
        self.edit_dns.setText(s.dns_server)

        self.chk_vlan.setChecked(s.vlan_enabled)
        self.edit_vlan.setText(str(s.vlan_id))
        self.edit_vlan.setEnabled(s.vlan_enabled)

        self.chk_mac.setChecked(s.custom_mac_enabled)
        self.edit_mac.setText(s.custom_mac)
        self.edit_mac.setEnabled(s.custom_mac_enabled)

        self.edit_ntp.setText(s.ntp_server or config.DEFAULT_NTP_SERVER)

        self._set_ip_mode(s.ip_mode)
        self._update_theme_buttons(ThemeManager.get_current_theme())

    def _set_ip_mode(self, mode: str):
        colors = ThemeManager.get_colors()
        self.manager.settings.ip_mode = mode
        is_static = (mode == "static")

        self.edit_ip.setEnabled(is_static)
        self.edit_prefix.setEnabled(is_static)
        self.edit_gw.setEnabled(is_static)
        self.edit_dns.setEnabled(is_static)

        active_style = f"background-color: {colors['accent_cyan']}; color: #ffffff; border: 1.5px solid {colors['accent_cyan']}; font-weight: 800;"
        inactive_style = f"background-color: {colors['bg_main']}; color: {colors['text_secondary']}; border: 1px solid {colors['card_border']};"

        self.btn_mode_dhcp.setStyleSheet(inactive_style if is_static else active_style)
        self.btn_mode_static.setStyleSheet(active_style if is_static else inactive_style)

    def _on_vlan_toggled(self, checked: bool):
        self.edit_vlan.setEnabled(checked)

    def _on_mac_toggled(self, checked: bool):
        self.edit_mac.setEnabled(checked)

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
            padding: 2px 8px;
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
