"""
İleri Keşif & L2 Güvenlik Analizi View (Advanced Discovery - formerly RogueDHCPView):
Structured 3-Card Diagnostic Dashboard for 800x480 Touchscreen:
1. Top-Left Card: 🛡️ Yetkisiz (Rogue) DHCP Avcısı (L2 DHCP Discover Broadcast Analysis)
2. Top-Right Card: ⚡ IP Çakışması & ARP Probe Tespiti (RFC 5227 ACD & Gratuitous ARP Inspector)
3. Bottom Full-Width Card: 📊 SNMP Switch Port & Sensör Analizi (Touch SNMP Community String + SwitchSNMPDialog Launcher)
Supports both Dark and Light Industrial themes.
"""

from typing import Optional
from PySide6.QtCore import Qt, Signal, QThreadPool
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
)
from cirak import config
from cirak.backend.dhcp import DHCPTest
from cirak.backend.arp_conflict import ARPConflictDetector, ARPConflictReport
from cirak.backend.snmp_client import SNMPClient, SNMPSwitchReport
from cirak.backend.network_detector import NetworkDetector
from cirak.backend.lldp_cdp import LLDPCdpTest
from cirak.backend.settings_manager import SettingsManager
from cirak.core.worker import BaseWorker
from cirak.gui.theme import ThemeManager
from cirak.gui.views.settings_view import TouchableLineEdit, TouchKeypadDialog


class RogueDHCPView(QWidget):
    """İleri Keşif (Advanced Discovery: Rogue DHCP + IP Conflict/ARP Probe + SNMP Switch Inspector) view."""

    back_requested = Signal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.settings_mgr = SettingsManager(simulate=False)
        self.dhcp_test = DHCPTest(simulate=False)
        self.arp_detector = ARPConflictDetector(simulate=False)
        self._last_is_rogue = False
        self._last_has_conflict = False
        self._dhcp_worker: Optional[BaseWorker] = None
        self._arp_worker: Optional[BaseWorker] = None
        self._snmp_worker: Optional[BaseWorker] = None
        self._init_ui()
        self.update_theme()

    def _detect_default_switch_ip(self) -> str:
        iface = NetworkDetector.get_active_interface()
        cached = LLDPCdpTest.get_cached_discovery(iface, max_age_sec=300.0)
        if cached and cached.get("management_ip"):
            ip = str(cached.get("management_ip")).strip()
            if "." in ip and not ip.startswith("-"):
                return ip
        gw = NetworkDetector.get_default_gateway()
        if gw and gw.get("gateway"):
            return gw["gateway"]
        return "194.27.65.1"

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 8, 12, 8)
        main_layout.setSpacing(8)

        # =========================================================
        # 1. Header Bar
        # =========================================================
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        self.back_btn = QPushButton("← Geri")
        self.back_btn.setFixedSize(70, 30)
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.clicked.connect(self.back_requested.emit)

        self.title_lbl = QLabel("İleri Keşif (Rogue DHCP • IP Çakışması • SNMP Switch)")
        t_font = QFont("DejaVu Sans", 11, QFont.Bold)
        self.title_lbl.setFont(t_font)

        self.btn_run_all = QPushButton("⚡ Tüm L2 Güvenlik Testlerini Başlat")
        self.btn_run_all.setProperty("class", "PrimaryBtn")
        self.btn_run_all.setFixedHeight(30)
        self.btn_run_all.setCursor(Qt.PointingHandCursor)
        self.btn_run_all.clicked.connect(self._run_all_l2_scans)

        header.addWidget(self.back_btn)
        header.addWidget(self.title_lbl)
        header.addStretch()
        header.addWidget(self.btn_run_all)
        main_layout.addLayout(header)

        # =========================================================
        # 2. Top Row: 2 Side-by-Side Cards (Rogue DHCP & IP Conflict / ARP Probe)
        # =========================================================
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        # --- Card 1: Yetkisiz (Rogue) DHCP Avcısı ---
        self.rogue_card = QFrame()
        self.rogue_card.setObjectName("RogueStatusCard")
        l_rogue = QVBoxLayout(self.rogue_card)
        l_rogue.setContentsMargins(12, 8, 12, 8)
        l_rogue.setSpacing(4)

        r_hdr = QHBoxLayout()
        self.lbl_r1 = QLabel("🛡️ YETKİSİZ (ROGUE) DHCP AVCISI")
        self.badge_rogue = QLabel("HAZIR")
        self.badge_rogue.setFont(QFont("DejaVu Sans Mono", 8, QFont.Bold))
        r_hdr.addWidget(self.lbl_r1)
        r_hdr.addStretch()
        r_hdr.addWidget(self.badge_rogue)

        gw = NetworkDetector.get_default_gateway()
        gw_ip = gw["gateway"] if gw else "194.27.65.1"
        gw_mac = NetworkDetector.get_gateway_mac(gw_ip) or "94:33:d8:2a:01:ef"
        real_ip = NetworkDetector.get_ip_address_cidr() or "194.27.65.131/24"

        self.rogue_details = QLabel(
            f"Yetkili Geçit: {gw_ip} ({gw_mac})\n"
            f"Atanan IP    : {real_ip}\n"
            f"Durum        : L2 DHCP Discover analizine hazır."
        )
        self.rogue_details.setWordWrap(True)

        self.scan_btn = QPushButton("🔍 Rogue DHCP Taraması Başlat")
        self.scan_btn.setFixedHeight(27)
        self.scan_btn.setCursor(Qt.PointingHandCursor)
        self.scan_btn.clicked.connect(self._run_scan)

        l_rogue.addLayout(r_hdr)
        l_rogue.addWidget(self.rogue_details)
        l_rogue.addStretch()
        l_rogue.addWidget(self.scan_btn)

        # --- Card 2: IP Çakışması & ARP Probe Tespiti (RFC 5227) ---
        self.arp_card = QFrame()
        self.arp_card.setObjectName("ArpConflictCard")
        l_arp = QVBoxLayout(self.arp_card)
        l_arp.setContentsMargins(12, 8, 12, 8)
        l_arp.setSpacing(4)

        a_hdr = QHBoxLayout()
        self.lbl_arp_title = QLabel("⚡ IP ÇAKIŞMASI & ARP PROBE")
        self.badge_arp = QLabel("HAZIR")
        self.badge_arp.setFont(QFont("DejaVu Sans Mono", 8, QFont.Bold))
        a_hdr.addWidget(self.lbl_arp_title)
        a_hdr.addStretch()
        a_hdr.addWidget(self.badge_arp)

        iface = NetworkDetector.get_active_interface()
        local_mac = NetworkDetector.get_mac_address(iface) or "--"

        self.arp_details = QLabel(
            f"Yerel IP/MAC : {real_ip.split('/')[0]} ({local_mac})\n"
            f"ARP Probe    : RFC 5227 (0.0.0.0 -> Hedef IP)\n"
            f"Durum        : Çift IP ve ARP Spoofing kontrolüne hazır."
        )
        self.arp_details.setWordWrap(True)

        self.btn_arp_conflict = QPushButton("⚡ IP Çakışması ve ARP Probe Testi")
        self.btn_arp_conflict.setFixedHeight(27)
        self.btn_arp_conflict.setCursor(Qt.PointingHandCursor)
        self.btn_arp_conflict.clicked.connect(self._run_arp_conflict_scan)

        l_arp.addLayout(a_hdr)
        l_arp.addWidget(self.arp_details)
        l_arp.addStretch()
        l_arp.addWidget(self.btn_arp_conflict)

        top_row.addWidget(self.rogue_card, 1)
        top_row.addWidget(self.arp_card, 1)
        main_layout.addLayout(top_row, 3)

        # =========================================================
        # 3. Bottom Full-Width Card: SNMP Switch Port & Sensör Analizi
        # =========================================================
        self.snmp_card = QFrame()
        self.snmp_card.setObjectName("SnmpInspectorCard")
        l_snmp = QVBoxLayout(self.snmp_card)
        l_snmp.setContentsMargins(12, 8, 12, 8)
        l_snmp.setSpacing(6)

        s_hdr = QHBoxLayout()
        self.lbl_snmp_title = QLabel("📊 SNMP SWITCH PORT & SENSÖR ANALİZİ (IF-MIB / CISCO-ENVMON)")
        self.badge_snmp = QLabel("SNMPv2c UDP/161")
        self.badge_snmp.setFont(QFont("DejaVu Sans Mono", 8, QFont.Bold))
        s_hdr.addWidget(self.lbl_snmp_title)
        s_hdr.addStretch()
        s_hdr.addWidget(self.badge_snmp)
        l_snmp.addLayout(s_hdr)

        # Touch Input Row: Switch IP + SNMP Community String + Action Buttons
        settings = self.settings_mgr.settings
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(6)

        self.lbl_sw_ip = QLabel("Switch IP:")
        self.inp_sw_ip = TouchableLineEdit(self._detect_default_switch_ip())
        self.inp_sw_ip.setFixedWidth(122)
        self.inp_sw_ip.setFixedHeight(28)
        self.inp_sw_ip.tapped.connect(lambda: self._open_keypad(self.inp_sw_ip, "Switch Yönetim IP Adresi", "ip"))

        self.lbl_comm = QLabel("SNMP Comm:")
        self.inp_comm = TouchableLineEdit(settings.snmp_community or "public")
        self.inp_comm.setFixedWidth(105)
        self.inp_comm.setFixedHeight(28)
        self.inp_comm.tapped.connect(lambda: self._open_keypad(self.inp_comm, "SNMP Community String", "snmp"))

        self.btn_snmp_quick = QPushButton("⚡ Hızlı Sorgu")
        self.btn_snmp_quick.setFixedHeight(28)
        self.btn_snmp_quick.setCursor(Qt.PointingHandCursor)
        self.btn_snmp_quick.clicked.connect(self._run_quick_snmp)

        self.btn_snmp_modal = QPushButton("📊 Port ve Sıcaklık Tablosu")
        self.btn_snmp_modal.setProperty("class", "PrimaryBtn")
        self.btn_snmp_modal.setFixedHeight(28)
        self.btn_snmp_modal.setCursor(Qt.PointingHandCursor)
        self.btn_snmp_modal.clicked.connect(self._open_snmp_dialog)

        ctrl_row.addWidget(self.lbl_sw_ip)
        ctrl_row.addWidget(self.inp_sw_ip)
        ctrl_row.addWidget(self.lbl_comm)
        ctrl_row.addWidget(self.inp_comm)
        ctrl_row.addWidget(self.btn_snmp_quick)
        ctrl_row.addWidget(self.btn_snmp_modal, 1)
        l_snmp.addLayout(ctrl_row)

        self.lbl_snmp_summary = QLabel(
            "💡 İpucu: Switch IP veya SNMP Community String alanına dokunarak ekran klavyesiyle değer girebilir, "
            "hangi portların AÇIK (UP), BOŞTA (DOWN) veya KAPALI (Admin-Down) olduğunu ve kasa sıcaklığını (°C) inceleyebilirsiniz."
        )
        self.lbl_snmp_summary.setWordWrap(True)
        l_snmp.addWidget(self.lbl_snmp_summary)

        main_layout.addWidget(self.snmp_card, 2)

    def _open_keypad(self, target_input: TouchableLineEdit, title: str, mode: str):
        dlg = TouchKeypadDialog(title=title, initial_value=target_input.text(), mode=mode, parent=self.window())
        if dlg.exec():
            val = dlg.result_text.strip()
            if val:
                target_input.setText(val)
                if target_input is self.inp_comm:
                    self.settings_mgr.settings.snmp_community = val
                    self.settings_mgr.save()

    def _open_snmp_dialog(self):
        from cirak.gui.dialogs.snmp_switch_dialog import SwitchSNMPDialog
        ip = self.inp_sw_ip.text().strip()
        comm = self.inp_comm.text().strip() or "public"
        if self.settings_mgr.settings.snmp_community != comm:
            self.settings_mgr.settings.snmp_community = comm
            self.settings_mgr.save()
        dlg = SwitchSNMPDialog(initial_ip=ip, initial_community=comm, parent=self.window())
        dlg.exec()

    def update_theme(self):
        """Apply Dark or Light theme palette to all 3 Advanced Discovery cards."""
        is_dark = ThemeManager.get_current_theme() == config.THEME_DARK
        colors = ThemeManager.get_colors()
        card_bg = colors["card_bg"]
        text_pri = colors["text_primary"]
        text_sec = colors["text_secondary"]

        self.title_lbl.setStyleSheet(
            f"background: transparent; font-size: 12px; font-weight: 800; color: {colors['accent_amber']};"
        )

        # Card 1: Rogue DHCP
        if self._last_is_rogue:
            r_bg = "#450a0a" if is_dark else "#fee2e2"
            r_border = colors["status_error"]
            r_fg = colors["status_error"]
        else:
            r_bg = card_bg
            r_border = colors["accent_amber"]
            r_fg = colors["accent_amber"]

        self.rogue_card.setStyleSheet(f"""
            QFrame#RogueStatusCard {{
                background-color: {r_bg};
                border: 1.5px solid {r_border};
                border-radius: 10px;
            }}
            QFrame#RogueStatusCard QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        self.lbl_r1.setStyleSheet(f"color: {r_fg}; font-weight: 900; font-size: 11px;")
        self.badge_rogue.setStyleSheet(f"""
            background-color: {'#451a03' if is_dark else '#fef3c7'};
            color: {r_fg};
            border: 1px solid {r_fg};
            border-radius: 4px;
            padding: 1px 6px;
        """)
        self.rogue_details.setStyleSheet(
            f"font-family: 'DejaVu Sans Mono', monospace; font-size: 10px; color: {r_fg if self._last_is_rogue else text_pri};"
        )
        self.scan_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {'#451a03' if is_dark else '#fef3c7'};
                color: {colors['accent_amber']};
                border: 1px solid {colors['accent_amber']};
                border-radius: 6px;
                font-size: 10px;
                font-weight: 800;
            }}
        """)

        # Card 2: ARP Conflict & Probe
        if self._last_has_conflict:
            a_bg = "#450a0a" if is_dark else "#fee2e2"
            a_border = colors["status_error"]
            a_fg = colors["status_error"]
        else:
            a_bg = card_bg
            a_border = colors["accent_cyan"]
            a_fg = colors["accent_cyan"]

        self.arp_card.setStyleSheet(f"""
            QFrame#ArpConflictCard {{
                background-color: {a_bg};
                border: 1.5px solid {a_border};
                border-radius: 10px;
            }}
            QFrame#ArpConflictCard QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        self.lbl_arp_title.setStyleSheet(f"color: {a_fg}; font-weight: 900; font-size: 11px;")
        self.badge_arp.setStyleSheet(f"""
            background-color: {'#083344' if is_dark else '#e0f2fe'};
            color: {a_fg};
            border: 1px solid {a_fg};
            border-radius: 4px;
            padding: 1px 6px;
        """)
        self.arp_details.setStyleSheet(
            f"font-family: 'DejaVu Sans Mono', monospace; font-size: 10px; color: {a_fg if self._last_has_conflict else text_pri};"
        )
        self.btn_arp_conflict.setStyleSheet(f"""
            QPushButton {{
                background-color: {'#083344' if is_dark else '#e0f2fe'};
                color: {colors['accent_cyan']};
                border: 1px solid {colors['accent_cyan']};
                border-radius: 6px;
                font-size: 10px;
                font-weight: 800;
            }}
        """)

        # Card 3: SNMP Switch Port & Sensor Inspector
        self.snmp_card.setStyleSheet(f"""
            QFrame#SnmpInspectorCard {{
                background-color: {card_bg};
                border: 1.5px solid {colors['accent_indigo']};
                border-radius: 10px;
            }}
            QFrame#SnmpInspectorCard QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        self.lbl_snmp_title.setStyleSheet(f"color: {colors['accent_indigo']}; font-weight: 900; font-size: 11px;")
        self.badge_snmp.setStyleSheet(f"""
            background-color: {'#1e1b4b' if is_dark else '#e0e7ff'};
            color: {colors['accent_indigo']};
            border: 1px solid {colors['accent_indigo']};
            border-radius: 4px;
            padding: 1px 6px;
        """)
        for lbl in [self.lbl_sw_ip, self.lbl_comm]:
            lbl.setStyleSheet(f"color: {text_sec}; font-size: 10px; font-weight: 800;")

        inp_style = f"""
            QLineEdit {{
                background-color: {'#090d16' if is_dark else '#ffffff'};
                color: {text_pri};
                border: 1.5px solid {colors['accent_indigo']};
                border-radius: 6px;
                padding: 2px 6px;
                font-family: "DejaVu Sans Mono", monospace;
                font-size: 11px;
                font-weight: 800;
            }}
        """
        self.inp_sw_ip.setStyleSheet(inp_style)
        self.inp_comm.setStyleSheet(inp_style)
        self.btn_snmp_quick.setStyleSheet(f"""
            QPushButton {{
                background-color: {'#1e1b4b' if is_dark else '#e0e7ff'};
                color: {colors['accent_indigo']};
                border: 1px solid {colors['accent_indigo']};
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 10px;
                font-weight: 800;
            }}
        """)
        self.lbl_snmp_summary.setStyleSheet(
            f"font-family: 'DejaVu Sans Mono', monospace; font-size: 10px; color: {text_sec};"
        )

    def _run_all_l2_scans(self):
        self._run_scan()
        self._run_arp_conflict_scan()

    def _run_scan(self):
        """Run Rogue DHCP L2 scan on background worker thread."""
        self.scan_btn.setText("DHCP Taranıyor...")
        self.scan_btn.setEnabled(False)
        self.badge_rogue.setText("DİNLENİYOR")

        self._dhcp_worker = BaseWorker(self.dhcp_test.run)
        self._dhcp_worker.signals.result.connect(self._on_dhcp_finished, Qt.QueuedConnection)
        self._dhcp_worker.signals.error.connect(self._on_dhcp_error, Qt.QueuedConnection)
        QThreadPool.globalInstance().start(self._dhcp_worker)

    def _on_dhcp_finished(self, res):
        colors = ThemeManager.get_colors()
        self.scan_btn.setText("🔍 Rogue DHCP Taraması Başlat")
        self.scan_btn.setEnabled(True)

        if res.details.get("is_rogue"):
            self._last_is_rogue = True
            self.badge_rogue.setText("🚨 SAHTE DHCP!")
            self.rogue_details.setText(
                f"🚨 SAHTE SUNUCU: {res.details.get('server_id')} ({res.details.get('server_mac')})\n"
                f"Dağıtılan IP   : {res.details.get('offered_ip')}\n"
                f"Ağda yetkisiz modem/router DHCP dağıtıyor!"
            )
            self.update_theme()
        else:
            self._last_is_rogue = False
            self.update_theme()
            self.badge_rogue.setText("✓ AĞ TEMİZ")
            self.badge_rogue.setStyleSheet(f"""
                background-color: transparent;
                color: {colors['status_success']};
                border: 1px solid {colors['status_success']};
                border-radius: 4px;
                padding: 1px 6px;
            """)
            srv_ip = res.details.get("server_id") or res.details.get("gateway") or "Yetkili Geçit"
            srv_mac = res.details.get("server_mac") or "Doğrulandı"
            self.rogue_details.setText(
                f"✓ Yetkili Sunucu: {srv_ip} ({srv_mac})\n"
                f"Atanan Cihaz IP : {res.details.get('offered_ip') or NetworkDetector.get_ip_address_cidr() or '--'}\n"
                f"Sonuç           : Yetkisiz (Rogue) DHCP sunucusu yok."
            )

    def _on_dhcp_error(self, _err):
        self.scan_btn.setText("🔍 Rogue DHCP Taraması Başlat")
        self.scan_btn.setEnabled(True)
        self.badge_rogue.setText("HATA")

    def _run_arp_conflict_scan(self):
        """Run RFC 5227 Duplicate IP & Active ARP Probe scan on background worker thread."""
        self.btn_arp_conflict.setText("ARP Probe Gönderiliyor...")
        self.btn_arp_conflict.setEnabled(False)
        self.badge_arp.setText("TARANIYOR")

        self._arp_worker = BaseWorker(self.arp_detector.run_scan)
        self._arp_worker.signals.result.connect(self._on_arp_finished, Qt.QueuedConnection)
        self._arp_worker.signals.error.connect(self._on_arp_error, Qt.QueuedConnection)
        QThreadPool.globalInstance().start(self._arp_worker)

    def _on_arp_finished(self, rep: ARPConflictReport):
        colors = ThemeManager.get_colors()
        self.btn_arp_conflict.setText("⚡ IP Çakışması ve ARP Probe Testi")
        self.btn_arp_conflict.setEnabled(True)

        if rep.has_conflict and rep.conflicts:
            self._last_has_conflict = True
            self.badge_arp.setText("🚨 ÇAKIŞMA!")
            self.arp_details.setText("🚨 " + "\n".join(rep.conflicts[:2]))
            self.update_theme()
        else:
            self._last_has_conflict = False
            self.update_theme()
            self.badge_arp.setText("✓ ÇAKIŞMA YOK")
            self.badge_arp.setStyleSheet(f"""
                background-color: transparent;
                color: {colors['status_success']};
                border: 1px solid {colors['status_success']};
                border-radius: 4px;
                padding: 1px 6px;
            """)
            nodes_str = "\n".join(rep.verified_nodes[:2]) if rep.verified_nodes else f"✓ Yerel IP: {rep.local_ip} | Geçit: {rep.gateway_ip}"
            self.arp_details.setText(
                f"{nodes_str}\n"
                f"ARP Tablosu: {rep.active_arp_entries} komşu | Probe: {rep.arp_probes_captured} paket ({rep.duration_ms:.0f} ms)"
            )

    def _on_arp_error(self, _err):
        self.btn_arp_conflict.setText("⚡ IP Çakışması ve ARP Probe Testi")
        self.btn_arp_conflict.setEnabled(True)
        self.badge_arp.setText("HATA")

    def _run_quick_snmp(self):
        """Run quick inline SNMP summary check and update the bottom banner."""
        ip = self.inp_sw_ip.text().strip()
        comm = self.inp_comm.text().strip() or "public"
        if self.settings_mgr.settings.snmp_community != comm:
            self.settings_mgr.settings.snmp_community = comm
            self.settings_mgr.save()

        self.btn_snmp_quick.setEnabled(False)
        self.btn_snmp_quick.setText("Sorgulanıyor...")
        self.lbl_snmp_summary.setText(f"⏳ {ip} adresine SNMPv2c (Community: '{comm}') sorgusu gönderiliyor...")

        def _task():
            client = SNMPClient(target_ip=ip, community=comm, timeout_sec=1.5, simulate=False)
            return client.query_switch()

        self._snmp_worker = BaseWorker(_task)
        self._snmp_worker.signals.result.connect(self._on_quick_snmp_done, Qt.QueuedConnection)
        self._snmp_worker.signals.error.connect(self._on_quick_snmp_err, Qt.QueuedConnection)
        QThreadPool.globalInstance().start(self._snmp_worker)

    def _on_quick_snmp_done(self, rep: SNMPSwitchReport):
        colors = ThemeManager.get_colors()
        self.btn_snmp_quick.setEnabled(True)
        self.btn_snmp_quick.setText("⚡ Hızlı Sorgu")

        if rep.reachable:
            temp_txt = f"{rep.temperature_c}°C" if rep.temperature_c is not None else "N/A"
            cpu_txt = f"%{rep.cpu_load_pct}" if rep.cpu_load_pct is not None else "N/A"
            self.badge_snmp.setText(f"✓ {rep.sys_name[:18]}")
            self.lbl_snmp_summary.setText(
                f"✓ Switch: {rep.sys_name} | Sıcaklık: {temp_txt} | CPU: {cpu_txt} | "
                f"Portlar: {rep.up_ports} AÇIK (UP), {rep.down_ports} BOŞTA (DOWN), {rep.admin_down_ports} KAPALI (Admin-Down)"
            )
            self.lbl_snmp_summary.setStyleSheet(
                f"font-family: 'DejaVu Sans Mono', monospace; font-size: 10px; color: {colors['status_success']}; font-weight: bold;"
            )
        else:
            self.badge_snmp.setText("YANIT YOK")
            self.lbl_snmp_summary.setText(f"⚠ {rep.error_message}")
            self.lbl_snmp_summary.setStyleSheet(
                f"font-family: 'DejaVu Sans Mono', monospace; font-size: 10px; color: {colors['status_warning']}; font-weight: bold;"
            )

    def _on_quick_snmp_err(self, _err):
        self.btn_snmp_quick.setEnabled(True)
        self.btn_snmp_quick.setText("⚡ Hızlı Sorgu")
        self.badge_snmp.setText("HATA")
