"""
Touch-Optimized Wi-Fi & DEÜ Eduroam (802.1X WPA2-Enterprise) Connection Dialog.
Supports:
  1. WPA2-Enterprise (802.1X / eduroam) with official DEÜ defaults (https://bid.deu.edu.tr/eduroam/):
     - EAP Method: TTLS (Default) or PEAP
     - Phase 2 Auth: PAP (Default for DEÜ TTLS) or MSCHAPV2
     - CA Certificate: Don't Validate (No external certificate file required)
     - Corporate Identity: ad.soyad@deu.edu.tr or ogrencino@ogr.deu.edu.tr
  2. WPA2-PSK / WPA3-SAE Personal Wi-Fi (Home / Lab / Hotspot)
  3. Open / Captive Portal Wi-Fi
Accessible from TopBar Wi-Fi icon, WiFiView table/button, and SettingsView.
"""

from typing import Optional
from PySide6.QtCore import Qt, Signal, QThreadPool
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QFrame,
    QLineEdit,
)
from cirak import config
from cirak.backend.settings_manager import SettingsManager
from cirak.backend.wifi_scanner import WiFiScanner
from cirak.core.worker import BaseWorker
from cirak.gui.theme import ThemeManager
from cirak.gui.views.settings_view import TouchableLineEdit, TouchKeypadDialog


class WiFiConnectDialog(QDialog):
    """Touchscreen Wi-Fi connection modal supporting 802.1X eduroam, WPA2/WPA3-PSK, and Open networks."""

    connection_changed = Signal(bool, str)

    def __init__(
        self,
        initial_ssid: str = "",
        initial_security: str = "",
        parent: QWidget = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Kablosuz Ağ (Wi-Fi / eduroam 802.1X) Bağlantısı")
        self.setFixedSize(710, 415)
        self.setModal(True)

        self.settings_mgr = SettingsManager(simulate=False)
        self.scanner = WiFiScanner(simulate=False)
        self._worker: Optional[BaseWorker] = None

        s = self.settings_mgr.settings
        self.ssid = initial_ssid or s.wifi_ssid or "eduroam"

        # Auto-detect auth mode from SSID or security string
        sec_low = initial_security.lower()
        if self.ssid.lower() == "eduroam" or any(k in sec_low for k in ("802.1x", "enterprise", "eap")):
            self.auth_mode = "eap"
        elif "open" in sec_low or "açık" in sec_low:
            self.auth_mode = "open"
        elif initial_ssid:
            self.auth_mode = "psk"
        else:
            self.auth_mode = s.wifi_auth_mode or "eap"

        self.eap_method = s.wifi_eap_method or "ttls"
        self.phase2_auth = s.wifi_phase2_auth or "pap"

        self._init_ui()
        self._apply_mode_ui()

    def _init_ui(self):
        colors = ThemeManager.get_colors()
        is_dark = ThemeManager.get_current_theme() == config.THEME_DARK
        input_bg = "#020617" if is_dark else "#f8fafc"

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg_main']};
                border: 2px solid {colors['accent_sky']};
                border-radius: 12px;
            }}
            QFrame#WiFiCard {{
                background-color: {colors['card_bg']};
                border: 1.5px solid {colors['card_border']};
                border-radius: 10px;
            }}
            QLabel {{
                background: transparent;
                border: none;
                color: {colors['text_primary']};
            }}
            QLineEdit {{
                background-color: {input_bg};
                color: {colors['text_primary']};
                border: 1.5px solid {colors['accent_sky']};
                border-radius: 6px;
                padding: 3px 8px;
                font-family: "DejaVu Sans Mono", monospace;
                font-size: 12px;
                font-weight: bold;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(7)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("📶 KABLOSUZ AĞ (Wi-Fi & DEÜ EDUROAM 802.1X) BAĞLANTISI")
        title.setStyleSheet(f"color: {colors['accent_sky']}; font-size: 13px; font-weight: 900;")

        ap_info = self.scanner.get_active_ap_telemetry()
        conn_txt = f"Bağlı: {ap_info['ssid']} ({ap_info['signal_dbm']} dBm)" if ap_info else "wlan0: Bağlı Değil"
        self.badge_conn = QLabel(conn_txt)
        self.badge_conn.setStyleSheet(f"""
            background-color: {'#022c22' if ap_info else ('#1e293b' if is_dark else '#e2e8f0')};
            color: {colors['status_success'] if ap_info else colors['text_secondary']};
            border: 1px solid {colors['status_success'] if ap_info else colors['card_border']};
            border-radius: 5px;
            padding: 2px 8px;
            font-family: monospace;
            font-size: 10px;
            font-weight: bold;
        """)

        hdr.addWidget(title)
        hdr.addStretch()
        hdr.addWidget(self.badge_conn)
        layout.addLayout(hdr)

        # Main Card
        card = QFrame()
        card.setObjectName("WiFiCard")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(12, 10, 12, 10)
        c_layout.setSpacing(7)

        # Row 1: SSID + Quick Campus SSID Presets
        ssid_row = QHBoxLayout()
        ssid_row.setSpacing(6)
        lbl_ssid = QLabel("Ağ Adı (SSID):")
        lbl_ssid.setStyleSheet(f"color: {colors['text_secondary']}; font-size: 11px; font-weight: 800;")
        self.edit_ssid = TouchableLineEdit(self.ssid)
        self.edit_ssid.setFixedHeight(28)
        self.edit_ssid.tapped.connect(lambda: self._open_kbd("Wi-Fi Ağ Adı (SSID)", self.edit_ssid, "host"))

        btn_kbd_ssid = QPushButton("ABC")
        btn_kbd_ssid.setFixedSize(44, 28)
        btn_kbd_ssid.setStyleSheet("font-size: 10px; font-weight: bold; padding: 1px 4px;")
        btn_kbd_ssid.clicked.connect(lambda: self._open_kbd("Wi-Fi Ağ Adı (SSID)", self.edit_ssid, "host"))

        ssid_row.addWidget(lbl_ssid)
        ssid_row.addWidget(self.edit_ssid, 1)
        ssid_row.addWidget(btn_kbd_ssid)

        for q_ssid, q_mode in (("eduroam", "eap"), ("DEU-Personel", "eap"), ("DEU-Misafir", "open")):
            q_btn = QPushButton(q_ssid)
            q_btn.setFixedHeight(26)
            q_btn.setCursor(Qt.PointingHandCursor)
            q_btn.setStyleSheet(
                f"font-size: 10px; font-weight: bold; padding: 2px 6px; color: {colors['accent_cyan']}; border: 1px solid {colors['card_border']}; border-radius: 5px;"
            )
            q_btn.clicked.connect(lambda checked=False, s_val=q_ssid, m_val=q_mode: self._select_quick_ssid(s_val, m_val))
            ssid_row.addWidget(q_btn)

        c_layout.addLayout(ssid_row)

        # Row 2: Security / Auth Mode Selector (3 Tactile Buttons)
        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        self.btn_mode_eap = QPushButton("🎓 Kurumsal 802.1X (eduroam)")
        self.btn_mode_eap.setFixedHeight(30)
        self.btn_mode_eap.setCursor(Qt.PointingHandCursor)
        self.btn_mode_eap.clicked.connect(lambda: self._set_auth_mode("eap"))

        self.btn_mode_psk = QPushButton("🔑 WPA2 / WPA3 Parola (PSK)")
        self.btn_mode_psk.setFixedHeight(30)
        self.btn_mode_psk.setCursor(Qt.PointingHandCursor)
        self.btn_mode_psk.clicked.connect(lambda: self._set_auth_mode("psk"))

        self.btn_mode_open = QPushButton("🔓 Açık Ağ (Şifresiz)")
        self.btn_mode_open.setFixedHeight(30)
        self.btn_mode_open.setCursor(Qt.PointingHandCursor)
        self.btn_mode_open.clicked.connect(lambda: self._set_auth_mode("open"))

        mode_row.addWidget(self.btn_mode_eap, 1)
        mode_row.addWidget(self.btn_mode_psk, 1)
        mode_row.addWidget(self.btn_mode_open, 1)
        c_layout.addLayout(mode_row)

        # Row 3: 802.1X EAP Parameters (TTLS/PEAP + Phase2 PAP/MSCHAPV2 + Cert Note)
        self.eap_params_frame = QFrame()
        eap_l = QHBoxLayout(self.eap_params_frame)
        eap_l.setContentsMargins(0, 0, 0, 0)
        eap_l.setSpacing(6)

        lbl_eap = QLabel("EAP:")
        lbl_eap.setStyleSheet(f"color: {colors['text_secondary']}; font-size: 10px; font-weight: bold;")
        self.btn_eap_ttls = QPushButton("TTLS (DEÜ)")
        self.btn_eap_ttls.setFixedHeight(26)
        self.btn_eap_ttls.clicked.connect(lambda: self._set_eap_method("ttls"))

        self.btn_eap_peap = QPushButton("PEAP")
        self.btn_eap_peap.setFixedHeight(26)
        self.btn_eap_peap.clicked.connect(lambda: self._set_eap_method("peap"))

        lbl_p2 = QLabel("Faz 2:")
        lbl_p2.setStyleSheet(f"color: {colors['text_secondary']}; font-size: 10px; font-weight: bold;")
        self.btn_p2_pap = QPushButton("PAP (DEÜ)")
        self.btn_p2_pap.setFixedHeight(26)
        self.btn_p2_pap.clicked.connect(lambda: self._set_phase2("pap"))

        self.btn_p2_mschap = QPushButton("MSCHAPv2")
        self.btn_p2_mschap.setFixedHeight(26)
        self.btn_p2_mschap.clicked.connect(lambda: self._set_phase2("mschapv2"))

        lbl_cert = QLabel("✓ Sertifika: Gerekmez (Doğrulama)")
        lbl_cert.setStyleSheet(f"color: {colors['status_success']}; font-size: 10px; font-weight: bold;")

        eap_l.addWidget(lbl_eap)
        eap_l.addWidget(self.btn_eap_ttls)
        eap_l.addWidget(self.btn_eap_peap)
        eap_l.addSpacing(6)
        eap_l.addWidget(lbl_p2)
        eap_l.addWidget(self.btn_p2_pap)
        eap_l.addWidget(self.btn_p2_mschap)
        eap_l.addStretch()
        eap_l.addWidget(lbl_cert)
        c_layout.addWidget(self.eap_params_frame)

        # Row 4 & 5: Identity & Password Grid
        cred_grid = QGridLayout()
        cred_grid.setHorizontalSpacing(8)
        cred_grid.setVerticalSpacing(6)

        self.lbl_identity = QLabel("Kurumsal E-Posta:")
        self.lbl_identity.setStyleSheet(f"color: {colors['text_secondary']}; font-size: 11px; font-weight: 800;")
        self.edit_identity = TouchableLineEdit(self.settings_mgr.settings.wifi_identity)
        self.edit_identity.setPlaceholderText("ad.soyad@deu.edu.tr veya ogrencino@ogr.deu.edu.tr")
        self.edit_identity.setFixedHeight(29)
        self.edit_identity.tapped.connect(
            lambda: self._open_kbd("Kurumsal E-Posta (eduroam Kimliği)", self.edit_identity, "email")
        )
        self.btn_kbd_id = QPushButton("ABC")
        self.btn_kbd_id.setFixedSize(44, 29)
        self.btn_kbd_id.setStyleSheet("font-size: 10px; font-weight: bold; padding: 1px 4px;")
        self.btn_kbd_id.clicked.connect(
            lambda: self._open_kbd("Kurumsal E-Posta (eduroam Kimliği)", self.edit_identity, "email")
        )

        self.lbl_password = QLabel("Ağ Parolası:")
        self.lbl_password.setStyleSheet(f"color: {colors['text_secondary']}; font-size: 11px; font-weight: 800;")
        self.edit_password = TouchableLineEdit("")
        self.edit_password.setPlaceholderText("Parolayı girmek için buraya dokunun...")
        self.edit_password.setEchoMode(QLineEdit.Password)
        self.edit_password.setFixedHeight(29)
        self.edit_password.tapped.connect(
            lambda: self._open_kbd("Wi-Fi / DEBİS Parolası", self.edit_password, "password")
        )

        pw_btn_box = QHBoxLayout()
        pw_btn_box.setSpacing(4)
        self.btn_toggle_pw = QPushButton("Göster")
        self.btn_toggle_pw.setFixedSize(56, 29)
        self.btn_toggle_pw.setStyleSheet("font-size: 10px; font-weight: bold; padding: 1px 4px;")
        self.btn_toggle_pw.setToolTip("Parolayı Göster / Gizle")
        self.btn_toggle_pw.clicked.connect(self._toggle_password_visibility)

        self.btn_kbd_pw = QPushButton("ABC")
        self.btn_kbd_pw.setFixedSize(44, 29)
        self.btn_kbd_pw.setStyleSheet("font-size: 10px; font-weight: bold; padding: 1px 4px;")
        self.btn_kbd_pw.clicked.connect(
            lambda: self._open_kbd("Wi-Fi / DEBİS Parolası", self.edit_password, "password")
        )
        pw_btn_box.addWidget(self.btn_toggle_pw)
        pw_btn_box.addWidget(self.btn_kbd_pw)

        cred_grid.addWidget(self.lbl_identity, 0, 0)
        cred_grid.addWidget(self.edit_identity, 0, 1)
        cred_grid.addWidget(self.btn_kbd_id, 0, 2)

        cred_grid.addWidget(self.lbl_password, 1, 0)
        cred_grid.addWidget(self.edit_password, 1, 1)
        cred_grid.addLayout(pw_btn_box, 1, 2)
        c_layout.addLayout(cred_grid)

        self.lbl_status = QLabel(
            "💡 Bilgi: Kablosuz bağlandığınızda (eth0 kablosu takılı değilken) tüm L1-L7 testleri, Hız Testi ve AP Keşfi wlan0 üzerinden çalışır."
        )
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet(f"color: {colors['text_secondary']}; font-size: 10px;")
        c_layout.addStretch()
        c_layout.addWidget(self.lbl_status)

        layout.addWidget(card, 1)

        # Bottom Action Row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_close = QPushButton("✕ Kapat")
        self.btn_close.setFixedHeight(36)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.clicked.connect(self.reject)

        self.btn_disconnect = QPushButton("🔌 Bağlantıyı Kes")
        self.btn_disconnect.setFixedHeight(36)
        self.btn_disconnect.setCursor(Qt.PointingHandCursor)
        self.btn_disconnect.setStyleSheet(
            "background-color: #7f1d1d; color: #ffffff; border: 1px solid #ef4444; border-radius: 6px; font-weight: 800;"
        )
        self.btn_disconnect.clicked.connect(self._on_disconnect_clicked)

        self.btn_connect = QPushButton("🔗 Şimdi Bağlan")
        self.btn_connect.setFixedHeight(36)
        self.btn_connect.setCursor(Qt.PointingHandCursor)
        self.btn_connect.setStyleSheet(
            "background-color: #0284c7; color: #ffffff; border: 1.5px solid #38bdf8; border-radius: 6px; font-size: 13px; font-weight: 900;"
        )
        self.btn_connect.clicked.connect(self._on_connect_clicked)

        btn_row.addWidget(self.btn_close, 1)
        btn_row.addWidget(self.btn_disconnect, 1)
        btn_row.addWidget(self.btn_connect, 2)
        layout.addLayout(btn_row)

    def _select_quick_ssid(self, ssid_val: str, mode_val: str):
        self.edit_ssid.setText(ssid_val)
        self._set_auth_mode(mode_val)

    def _set_auth_mode(self, mode: str):
        self.auth_mode = mode
        self._apply_mode_ui()

    def _set_eap_method(self, method: str):
        self.eap_method = method
        if method == "ttls":
            self.phase2_auth = "pap"
        elif method == "peap":
            self.phase2_auth = "mschapv2"
        self._apply_mode_ui()

    def _set_phase2(self, p2: str):
        self.phase2_auth = p2
        self._apply_mode_ui()

    def _apply_mode_ui(self):
        colors = ThemeManager.get_colors()
        act_qss = f"background-color: {colors['accent_sky']}; color: #ffffff; border: 1.5px solid {colors['accent_cyan']}; border-radius: 6px; font-weight: 900; font-size: 11px;"
        inact_qss = f"background-color: {colors['bg_main']}; color: {colors['text_secondary']}; border: 1px solid {colors['card_border']}; border-radius: 6px; font-weight: 700; font-size: 11px;"

        self.btn_mode_eap.setStyleSheet(act_qss if self.auth_mode == "eap" else inact_qss)
        self.btn_mode_psk.setStyleSheet(act_qss if self.auth_mode == "psk" else inact_qss)
        self.btn_mode_open.setStyleSheet(act_qss if self.auth_mode == "open" else inact_qss)

        sub_act = f"background-color: {colors['accent_indigo']}; color: #ffffff; border: 1px solid {colors['accent_indigo']}; border-radius: 5px; font-size: 10px; font-weight: 900; padding: 2px 8px;"
        sub_inact = f"background-color: {colors['bg_main']}; color: {colors['text_secondary']}; border: 1px solid {colors['card_border']}; border-radius: 5px; font-size: 10px; padding: 2px 8px;"

        self.btn_eap_ttls.setStyleSheet(sub_act if self.eap_method == "ttls" else sub_inact)
        self.btn_eap_peap.setStyleSheet(sub_act if self.eap_method == "peap" else sub_inact)
        self.btn_p2_pap.setStyleSheet(sub_act if self.phase2_auth == "pap" else sub_inact)
        self.btn_p2_mschap.setStyleSheet(sub_act if self.phase2_auth == "mschapv2" else sub_inact)

        is_eap = self.auth_mode == "eap"
        is_open = self.auth_mode == "open"

        self.eap_params_frame.setVisible(is_eap)
        self.lbl_identity.setVisible(is_eap)
        self.edit_identity.setVisible(is_eap)
        self.btn_kbd_id.setVisible(is_eap)

        self.lbl_password.setVisible(not is_open)
        self.edit_password.setVisible(not is_open)
        self.btn_toggle_pw.setVisible(not is_open)
        self.btn_kbd_pw.setVisible(not is_open)
        self.lbl_password.setText("DEBİS / E-Posta Parolası:" if is_eap else "Wi-Fi Ağ Parolası:")

    def _toggle_password_visibility(self):
        if self.edit_password.echoMode() == QLineEdit.Password:
            self.edit_password.setEchoMode(QLineEdit.Normal)
        else:
            self.edit_password.setEchoMode(QLineEdit.Password)

    def _open_kbd(self, title: str, line_edit: QLineEdit, mode: str):
        dlg = TouchKeypadDialog(title=title, initial_value=line_edit.text(), mode=mode, parent=self)
        if dlg.exec() == QDialog.Accepted:
            line_edit.setText(dlg.result_text)

    def _on_connect_clicked(self):
        ssid = self.edit_ssid.text().strip()
        identity = self.edit_identity.text().strip()
        password = self.edit_password.text()

        # Persist non-sensitive profile defaults
        s = self.settings_mgr.settings
        s.wifi_ssid = ssid
        s.wifi_auth_mode = self.auth_mode
        s.wifi_eap_method = self.eap_method
        s.wifi_phase2_auth = self.phase2_auth
        if self.auth_mode == "eap":
            s.wifi_identity = identity
        self.settings_mgr.save()

        self.btn_connect.setEnabled(False)
        self.btn_connect.setText("Bağlanıyor...")
        self.lbl_status.setText(f"⏳ {ssid} ağına bağlanılıyor (Kimlik doğrulama ve DHCP bekleniyor)...")
        self.lbl_status.setStyleSheet("color: #f59e0b; font-size: 11px; font-weight: bold;")

        def _task():
            return self.scanner.connect_network(
                ssid=ssid,
                auth_mode=self.auth_mode,
                identity=identity,
                password=password,
                eap_method=self.eap_method,
                phase2_auth=self.phase2_auth,
            )

        self._worker = BaseWorker(_task)
        self._worker.signals.result.connect(self._on_connect_finished, Qt.QueuedConnection)
        self._worker.signals.error.connect(self._on_connect_error, Qt.QueuedConnection)
        QThreadPool.globalInstance().start(self._worker)

    def _on_connect_finished(self, res: tuple):
        colors = ThemeManager.get_colors()
        self.btn_connect.setEnabled(True)
        self.btn_connect.setText("🔗 Şimdi Bağlan")
        ok, msg = res
        self.lbl_status.setText(msg)
        self.lbl_status.setStyleSheet(
            f"color: {colors['status_success'] if ok else colors['status_error']}; font-size: 11px; font-weight: bold;"
        )
        if ok:
            self.badge_conn.setText(f"✓ Bağlı: {self.edit_ssid.text().strip()}")
            self.connection_changed.emit(True, self.edit_ssid.text().strip())

    def _on_connect_error(self, err_tuple):
        self.btn_connect.setEnabled(True)
        self.btn_connect.setText("🔗 Şimdi Bağlan")
        self.lbl_status.setText("Bağlantı sırasında beklenmeyen bir hata oluştu.")

    def _on_disconnect_clicked(self):
        ok, msg = self.scanner.disconnect_network()
        colors = ThemeManager.get_colors()
        self.lbl_status.setText(msg)
        self.lbl_status.setStyleSheet(f"color: {colors['status_warning']}; font-size: 11px; font-weight: bold;")
        self.badge_conn.setText("wlan0: Bağlı Değil")
        self.connection_changed.emit(False, "")
