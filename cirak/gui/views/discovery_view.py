"""
Network Discovery & Switch Diagnostic View:
1. Top-Left: Subnet IP Occupancy Rate (% and Active/254 count with progress bar)
2. Top-Right: Switch Port LED Flasher with Fluke-style Cadence Slider (Cisco err-disable safe)
3. Bottom Full-Width Panel: Connected Network Switch (CDP / LLDP / 802.1X NAC / STP / Unauthorized Switch Inspector)
Includes live 2-second background L2 cache polling and full Dark/Light theme consistency.
"""

from typing import Optional
from PySide6.QtCore import Qt, Signal, QThreadPool, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QFrame,
    QSlider,
    QProgressBar,
)
from cirak import config
from cirak.backend.lldp_cdp import LLDPCdpTest
from cirak.backend.port_blinker import PortBlinker
from cirak.backend.arp_scanner import ARPScanner
from cirak.backend.network_detector import NetworkDetector
from cirak.core.models import TestResult
from cirak.core.worker import BaseWorker
from cirak.gui.theme import ThemeManager


class DiscoveryView(QWidget):
    """Network discovery and switch inspection view optimized for 7-inch 800x480 touchscreen."""

    back_requested = Signal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.blinker = PortBlinker(simulate=False)
        self.arp_scanner = ARPScanner(simulate=False)
        self._lldp_worker: Optional[BaseWorker] = None
        self._arp_worker: Optional[BaseWorker] = None
        self._last_switch_data: Optional[dict] = None

        # Start continuous background L2 sniffer so CDP (60s) and 802.1X NAC frames are never missed
        LLDPCdpTest.ensure_background_listener()

        self._init_ui()
        self.update_theme()

        # Live 2.5s timer to auto-update Switch Panel when background CDP/LLDP/NAC frame arrives
        self._live_timer = QTimer(self)
        self._live_timer.timeout.connect(self._refresh_cached_switch_info)
        self._live_timer.start(2500)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 8, 12, 8)
        main_layout.setSpacing(8)

        # =========================================================
        # 1. Header Bar
        # =========================================================
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)

        self.back_btn = QPushButton("← Geri")
        self.back_btn.setFixedSize(70, 30)
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.clicked.connect(self.back_requested.emit)

        self.title_lbl = QLabel("Ağ Keşfi & Anahtarlama Cihazı (Switch) Analizi")
        t_font = QFont("DejaVu Sans", 11, QFont.Bold)
        self.title_lbl.setFont(t_font)

        header.addWidget(self.back_btn)
        header.addWidget(self.title_lbl)
        header.addStretch()

        # =========================================================
        # 2. Top Row: 2 Compact Cards (IP Occupancy % & Port Blinker Slider)
        # =========================================================
        top_cards_layout = QHBoxLayout()
        top_cards_layout.setSpacing(10)

        # --- Card 1: IP Doluluk Oranı (ARP Occupancy) ---
        self.card_arp = QFrame()
        self.card_arp.setObjectName("DiscoveryTopCard")
        l_arp = QVBoxLayout(self.card_arp)
        l_arp.setContentsMargins(12, 8, 12, 8)
        l_arp.setSpacing(4)

        arp_hdr = QHBoxLayout()
        self.lbl_arp_title = QLabel("📊 IP Doluluk Oranı")
        self.lbl_subnet_tag = QLabel("Alt Ağ: /24")
        arp_hdr.addWidget(self.lbl_arp_title)
        arp_hdr.addStretch()
        arp_hdr.addWidget(self.lbl_subnet_tag)

        self.lbl_arp_value = QLabel("-- % (-- / 254 Aktif IP)")
        val_font = QFont("DejaVu Sans Mono", 13, QFont.Bold)
        self.lbl_arp_value.setFont(val_font)

        self.arp_progress = QProgressBar()
        self.arp_progress.setFixedHeight(6)
        self.arp_progress.setRange(0, 254)
        self.arp_progress.setValue(0)
        self.arp_progress.setTextVisible(False)

        self.btn_run_arp = QPushButton("IP Doluluk Oranını Ölç")
        self.btn_run_arp.setProperty("class", "PrimaryBtn")
        self.btn_run_arp.setFixedHeight(26)
        self.btn_run_arp.setCursor(Qt.PointingHandCursor)
        self.btn_run_arp.clicked.connect(self._run_arp_sweep)

        l_arp.addLayout(arp_hdr)
        l_arp.addWidget(self.lbl_arp_value)
        l_arp.addWidget(self.arp_progress)
        l_arp.addStretch()
        l_arp.addWidget(self.btn_run_arp)

        # --- Card 2: Port Işıkları (Flaşör & Cisco err-disable Safe Slider) ---
        self.card_blink = QFrame()
        self.card_blink.setObjectName("DiscoveryBlinkCard")
        l_blink = QVBoxLayout(self.card_blink)
        l_blink.setContentsMargins(12, 8, 12, 8)
        l_blink.setSpacing(4)

        blink_hdr = QHBoxLayout()
        self.lbl_blink_title = QLabel("💡 Port Işıkları (Flaşör)")
        self.lbl_blink_rate = QLabel("Periyot: 4.0 sn (Cisco Güvenli)")
        blink_hdr.addWidget(self.lbl_blink_title)
        blink_hdr.addStretch()
        blink_hdr.addWidget(self.lbl_blink_rate)

        slider_row = QHBoxLayout()
        self.lbl_fast = QLabel("Hızlı (1s)")
        self.blink_slider = QSlider(Qt.Horizontal)
        self.blink_slider.setRange(10, 50)
        self.blink_slider.setValue(40)  # Default 4.0s (safe against Cisco link-flap err-disable)
        self.blink_slider.setFixedHeight(20)
        self.blink_slider.valueChanged.connect(self._on_slider_changed)
        self.lbl_safe = QLabel("Güvenli (5s)")

        slider_row.addWidget(self.lbl_fast)
        slider_row.addWidget(self.blink_slider)
        slider_row.addWidget(self.lbl_safe)

        self.blink_status = QLabel("Cisco portlarının kapanmaması (err-disable) için ≥3 sn önerilir.")

        self.btn_toggle_blink = QPushButton("Flaşörü Başlat (Blink)")
        self.btn_toggle_blink.setFixedHeight(26)
        self.btn_toggle_blink.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_blink.clicked.connect(self._toggle_blinker)

        l_blink.addLayout(blink_hdr)
        l_blink.addLayout(slider_row)
        l_blink.addWidget(self.blink_status)
        l_blink.addStretch()
        l_blink.addWidget(self.btn_toggle_blink)

        top_cards_layout.addWidget(self.card_arp, 1)
        top_cards_layout.addWidget(self.card_blink, 1)

        # =========================================================
        # 3. Bottom Large Box: Connected Switch (Ağ Anahtarlama Cihazı)
        # =========================================================
        self.switch_panel = QFrame()
        self.switch_panel.setObjectName("SwitchInspectorPanel")
        sw_layout = QVBoxLayout(self.switch_panel)
        sw_layout.setContentsMargins(14, 10, 14, 10)
        sw_layout.setSpacing(6)

        # Switch Panel Header
        sw_hdr = QHBoxLayout()
        self.lbl_sw_title = QLabel("🔍 BAĞLI AĞ ANAHTARLAMA CİHAZI (SWITCH / AP)")

        self.proto_badge = QLabel("DİNLENİYOR")
        self.proto_badge.setFont(QFont("DejaVu Sans Mono", 9, QFont.Bold))

        self.btn_snmp_inspect = QPushButton("📊 SNMP ile İncele")
        self.btn_snmp_inspect.setFixedHeight(28)
        self.btn_snmp_inspect.setCursor(Qt.PointingHandCursor)
        self.btn_snmp_inspect.setToolTip("SNMP Comm String ile Switch Port Durumlarını ve Sıcaklığı İncele")
        self.btn_snmp_inspect.clicked.connect(self._open_snmp_dialog)

        self.btn_read_lldp = QPushButton("🔍 CDP / LLDP Dinle")
        self.btn_read_lldp.setProperty("class", "PrimaryBtn")
        self.btn_read_lldp.setFixedHeight(28)
        self.btn_read_lldp.setCursor(Qt.PointingHandCursor)
        self.btn_read_lldp.clicked.connect(self._run_lldp_query)

        sw_hdr.addWidget(self.lbl_sw_title)
        sw_hdr.addStretch()
        sw_hdr.addWidget(self.proto_badge)
        sw_hdr.addWidget(self.btn_snmp_inspect)
        sw_hdr.addWidget(self.btn_read_lldp)
        sw_layout.addLayout(sw_hdr)

        # Divider
        self.sw_div = QFrame()
        self.sw_div.setFrameShape(QFrame.HLine)
        sw_layout.addWidget(self.sw_div)

        # 2-Column Telemetry Grid inside Switch Box (4 rows, with IOS version below Marka/Model)
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(4)
        grid.setContentsMargins(2, 2, 2, 2)

        self.lbl_k_name = QLabel("Cihaz Adı (Switch):")
        self.val_sw_name = QLabel("Bekleniyor...")

        self.lbl_k_model = QLabel("Marka / Model:")
        self.val_sw_model = QLabel("--")

        self.lbl_k_ios = QLabel("Yazılım / IOS Sürümü:")
        self.val_sw_ios = QLabel("--")

        self.lbl_k_mgmt = QLabel("Yönetim IP Adresi:")
        self.val_sw_mgmt = QLabel("--")

        self.lbl_k_port = QLabel("Bağlı Port (Port ID):")
        self.val_sw_port = QLabel("--")

        self.lbl_k_vlan = QLabel("VLAN (Native / Tag):")
        self.val_sw_vlan = QLabel("--")

        self.lbl_k_mac = QLabel("Switch MAC / Üretici:")
        self.val_sw_mac = QLabel("--")

        self._key_labels = [
            self.lbl_k_name, self.lbl_k_model, self.lbl_k_ios, self.lbl_k_mgmt,
            self.lbl_k_port, self.lbl_k_vlan, self.lbl_k_mac,
        ]

        # Row 0: Switch Name | Connected Port
        grid.addWidget(self.lbl_k_name, 0, 0)
        grid.addWidget(self.val_sw_name, 0, 1)
        grid.addWidget(self.lbl_k_port, 0, 2)
        grid.addWidget(self.val_sw_port, 0, 3)

        # Row 1: Brand / Model | VLAN ID
        grid.addWidget(self.lbl_k_model, 1, 0)
        grid.addWidget(self.val_sw_model, 1, 1)
        grid.addWidget(self.lbl_k_vlan, 1, 2)
        grid.addWidget(self.val_sw_vlan, 1, 3)

        # Row 2: Software / IOS Version (directly below Marka / Model, spanning columns 1..3)
        grid.addWidget(self.lbl_k_ios, 2, 0)
        grid.addWidget(self.val_sw_ios, 2, 1, 1, 3)

        # Row 3: Management IP | Switch MAC / Vendor
        grid.addWidget(self.lbl_k_mgmt, 3, 0)
        grid.addWidget(self.val_sw_mgmt, 3, 1)
        grid.addWidget(self.lbl_k_mac, 3, 2)
        grid.addWidget(self.val_sw_mac, 3, 3)

        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        sw_layout.addLayout(grid)

        # Security / Diagnostic Note Banner at bottom of Switch Panel
        self.lbl_sw_Diagnostic = QLabel(
            "💡 Bilgi: Arka plan dinleyicisi Cisco CDP (60 sn), IEEE LLDP, 802.1X NAC, PVST+ ve L2 Ağ Geçidi bilgilerini yakalar."
        )
        self.lbl_sw_Diagnostic.setWordWrap(True)
        sw_layout.addStretch()
        sw_layout.addWidget(self.lbl_sw_Diagnostic)

        main_layout.addLayout(header)
        main_layout.addLayout(top_cards_layout, 2)
        main_layout.addWidget(self.switch_panel, 3)

        # Populate initial passive data if daemon or background sniffer already cached CDP/LLDP
        self._gw_probe_running = False
        self._refresh_cached_switch_info()

    def update_theme(self):
        """Apply active theme palette (Dark or Light) consistently across all cards and controls."""
        is_dark = ThemeManager.get_current_theme() == config.THEME_DARK
        colors = ThemeManager.get_colors()
        card_bg = colors["card_bg"]
        border_col = colors["card_border"]
        text_pri = colors["text_primary"]
        text_sec = colors["text_secondary"]
        text_mut = colors["text_muted"]

        self.title_lbl.setStyleSheet(f"background: transparent; color: {colors['accent_indigo']}; font-weight: 800;")

        # Card 1: ARP IP Occupancy
        self.card_arp.setStyleSheet(f"""
            QFrame#DiscoveryTopCard {{
                background-color: {card_bg};
                border: 1.5px solid {colors['status_success']};
                border-radius: 10px;
            }}
            QFrame#DiscoveryTopCard QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        self.lbl_arp_title.setStyleSheet(f"font-weight: 800; color: {colors['status_success']}; font-size: 11px;")
        self.lbl_subnet_tag.setStyleSheet(f"font-family: monospace; font-size: 10px; color: {text_sec};")
        self.lbl_arp_value.setStyleSheet(f"color: {text_pri}; font-weight: 900;")
        self.arp_progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: {border_col};
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: {colors['status_success']};
                border-radius: 3px;
            }}
        """)

        # Card 2: Port Blinker
        blink_accent = "#a855f7" if is_dark else "#7e22ce"
        self.card_blink.setStyleSheet(f"""
            QFrame#DiscoveryBlinkCard {{
                background-color: {card_bg};
                border: 1.5px solid {blink_accent};
                border-radius: 10px;
            }}
            QFrame#DiscoveryBlinkCard QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        self.lbl_blink_title.setStyleSheet(f"font-weight: 800; color: {blink_accent}; font-size: 11px;")
        self.lbl_fast.setStyleSheet(f"font-size: 9px; color: {colors['status_warning']}; font-weight: bold;")
        self.lbl_safe.setStyleSheet(f"font-size: 9px; color: {colors['status_success']}; font-weight: bold;")
        self.blink_status.setStyleSheet(f"font-size: 9px; color: {text_sec};")
        self._on_slider_changed(self.blink_slider.value())

        # Card 3: Switch Inspector Panel
        self.switch_panel.setStyleSheet(f"""
            QFrame#SwitchInspectorPanel {{
                background-color: {card_bg};
                border: 1.5px solid {colors['accent_indigo']};
                border-radius: 12px;
            }}
            QFrame#SwitchInspectorPanel QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        self.lbl_sw_title.setStyleSheet(f"font-weight: 900; color: {colors['accent_indigo']}; font-size: 12px;")
        self.sw_div.setStyleSheet(f"background-color: {border_col}; max-height: 1px;")

        self.btn_snmp_inspect.setStyleSheet(f"""
            QPushButton {{
                background-color: {'#1e1b4b' if is_dark else '#e0e7ff'};
                color: {colors['accent_indigo']};
                border: 1.5px solid {colors['accent_indigo']};
                border-radius: 6px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: 800;
            }}
            QPushButton:pressed {{
                background-color: {colors['accent_indigo']};
                color: #ffffff;
            }}
        """)

        for kl in self._key_labels:
            kl.setStyleSheet(f"color: {text_mut}; font-size: 10px; font-weight: 700;")

        val_style = f"color: {text_pri}; font-family: 'DejaVu Sans Mono', monospace; font-size: 11px; font-weight: 800;"
        self.val_sw_name.setStyleSheet(
            f"color: {colors['accent_cyan']}; font-family: 'DejaVu Sans Mono', monospace; font-size: 11px; font-weight: 900;"
        )
        self.val_sw_model.setStyleSheet(val_style)
        self.val_sw_ios.setStyleSheet(
            f"color: {colors['accent_indigo']}; font-family: 'DejaVu Sans Mono', monospace; font-size: 11px; font-weight: 900;"
        )
        self.val_sw_mgmt.setStyleSheet(val_style)
        self.val_sw_port.setStyleSheet(
            f"color: {colors['status_success']}; font-family: 'DejaVu Sans Mono', monospace; font-size: 11px; font-weight: 900;"
        )
        self.val_sw_vlan.setStyleSheet(
            f"color: {colors['status_warning']}; font-family: 'DejaVu Sans Mono', monospace; font-size: 11px; font-weight: 900;"
        )
        self.val_sw_mac.setStyleSheet(val_style)

        if self._last_switch_data:
            self._populate_switch_panel(self._last_switch_data)
        else:
            self.proto_badge.setStyleSheet(f"""
                background-color: rgba(99, 102, 241, 0.15);
                color: {colors['accent_indigo']};
                border: 1px solid {colors['accent_indigo']};
                border-radius: 4px;
                padding: 2px 8px;
            """)
            self.lbl_sw_Diagnostic.setStyleSheet(f"color: {text_sec}; font-size: 10px; font-family: monospace;")

    def _open_snmp_dialog(self):
        """Open touch-optimized SNMP Switch Port & Sensor Inspector modal."""
        from cirak.gui.dialogs.snmp_switch_dialog import SwitchSNMPDialog
        raw_ip = self.val_sw_mgmt.text().strip()
        target_ip = raw_ip if ("." in raw_ip and not raw_ip.startswith("-")) else ""
        dlg = SwitchSNMPDialog(initial_ip=target_ip, parent=self.window())
        dlg.exec()

    def _on_slider_changed(self, value: int):
        colors = ThemeManager.get_colors()
        sec = value / 10.0
        self.blinker.set_interval(sec)
        if sec >= 3.0:
            tag = "Cisco Güvenli"
            color = colors["status_success"]
        elif sec >= 2.0:
            tag = "Normal"
            color = colors["accent_indigo"]
        else:
            tag = "Hızlı - Dikkat!"
            color = colors["status_warning"]
        self.lbl_blink_rate.setText(f"Periyot: {sec:.1f} sn ({tag})")
        self.lbl_blink_rate.setStyleSheet(
            f"background: transparent; font-family: monospace; font-size: 10px; color: {color}; font-weight: bold;"
        )

    def _toggle_blinker(self):
        colors = ThemeManager.get_colors()
        if self.blinker.is_blinking:
            self.blinker.stop_blink()
            self.btn_toggle_blink.setText("Flaşörü Başlat (Blink)")
            self.blink_status.setText("Flaşör durduruldu.")
            self.blink_status.setStyleSheet(f"background: transparent; font-size: 9px; color: {colors['text_secondary']};")
        else:
            sec = self.blink_slider.value() / 10.0
            self.btn_toggle_blink.setText("⏹ Flaşörü Durdur [AKTİF]")
            self.blink_status.setText(f"Port LED {sec:.1f} sn periyotla güvenli şekilde yanıp sönüyor...")
            self.blink_status.setStyleSheet(
                f"background: transparent; font-size: 9px; color: {colors['accent_indigo']}; font-weight: bold;"
            )
            self.blinker.start_blink(duration_sec=30, interval_sec=sec)

    def _refresh_cached_switch_info(self):
        """Non-blocking check of lldpd, continuous background raw L2 sniffer cache, and L2/L3 gateway fallback."""
        iface = NetworkDetector.get_active_interface()
        cached = NetworkDetector.get_lldp_from_daemon(iface)
        if cached and cached.get("system_name"):
            self._populate_switch_panel(cached)
            return

        bg = LLDPCdpTest.get_cached_discovery(iface, max_age_sec=180.0)
        if bg and (bg.get("system_name") or bg.get("port_id")):
            self._populate_switch_panel(bg)
            return

        # If no CDP/LLDP is cached yet, probe active L2/L3 gateway (e.g. TP-Link / home router) in background once
        if not self._gw_probe_running and not self._last_switch_data:
            self._gw_probe_running = True

            def _gw_task():
                return NetworkDetector.probe_gateway_device(iface)

            gw_worker = BaseWorker(_gw_task)
            gw_worker.signals.result.connect(self._on_gw_probe_finished, Qt.QueuedConnection)
            gw_worker.signals.error.connect(lambda _: setattr(self, "_gw_probe_running", False), Qt.QueuedConnection)
            QThreadPool.globalInstance().start(gw_worker)

    def _on_gw_probe_finished(self, gw_data: Optional[dict]):
        self._gw_probe_running = False
        if gw_data and (gw_data.get("system_name") or gw_data.get("chassis_id")):
            # Only populate if a full CDP/LLDP frame hasn't already arrived
            if not self._last_switch_data or not str(self._last_switch_data.get("protocol", "")).startswith(("CDP", "LLDP")):
                self._populate_switch_panel(gw_data)

    def _run_lldp_query(self):
        """Run active CDP/LLDP/NAC/L2 capture on background worker thread."""
        self.btn_read_lldp.setText("Dinleniyor...")
        self.btn_read_lldp.setEnabled(False)
        self.proto_badge.setText("PAKET BEKLENİYOR")

        def _task():
            test = LLDPCdpTest(timeout_sec=5.0, simulate=False)
            return test.run()

        self._lldp_worker = BaseWorker(_task)
        self._lldp_worker.signals.result.connect(self._on_lldp_finished, Qt.QueuedConnection)
        self._lldp_worker.signals.error.connect(self._on_lldp_error, Qt.QueuedConnection)
        QThreadPool.globalInstance().start(self._lldp_worker)

    def _on_lldp_finished(self, res: TestResult):
        self.btn_read_lldp.setText("🔍 CDP / LLDP Dinle")
        self.btn_read_lldp.setEnabled(True)
        self._populate_switch_panel(res.details)

    def _on_lldp_error(self, err_tuple):
        self.btn_read_lldp.setText("🔍 CDP / LLDP Dinle")
        self.btn_read_lldp.setEnabled(True)
        self.proto_badge.setText("HATA")

    def _populate_switch_panel(self, d: dict):
        self._last_switch_data = d
        is_dark = ThemeManager.get_current_theme() == config.THEME_DARK
        colors = ThemeManager.get_colors()

        if d.get("system_name") or d.get("port_id"):
            proto = d.get("protocol", "CDP/LLDP")
            is_unauth = d.get("is_unauthorized_switch", False)
            nac_active = d.get("nac_active", False)
            vendor_str = str(d.get("vendor") or "")

            self.val_sw_name.setText(str(d.get("system_name") or "Tespit Edildi"))

            raw_descr = str(d.get("system_description") or "")
            raw_sw = str(d.get("software_version") or "")
            model_clean, sw_clean = NetworkDetector.extract_model_and_ios(
                raw_descr, sw_ver=raw_sw, vendor=vendor_str
            )
            model_display = model_clean or vendor_str or "Kurumsal Switch"
            self.val_sw_model.setText(str(model_display)[:42])

            if sw_clean:
                self.val_sw_ios.setText(str(sw_clean)[:68])
            elif "L2-ARP" in proto:
                self.val_sw_ios.setText("SOHO / Standart Firmware (CDP/LLDP Yok)")
            else:
                self.val_sw_ios.setText("Bildirilmedi (CDP/LLDP Paketi Bekleniyor)")

            self.val_sw_mgmt.setText(str(d.get("management_ip") or "Bildirilmedi"))

            port_str = str(d.get("port_id") or "Bilinmiyor")
            if d.get("port_description") and d.get("port_description") not in port_str:
                port_str += f" ({d.get('port_description')[:18]})"
            self.val_sw_port.setText(port_str)

            vlan_str = f"VLAN {d.get('vlan_id')}" if d.get("vlan_id") else "Untagged / Native"
            if d.get("vlan_name"):
                vlan_str += f" ({d.get('vlan_name')})"
            self.val_sw_vlan.setText(vlan_str)

            mac_str = str(d.get("chassis_id") or "--")
            self.val_sw_mac.setText(f"{mac_str} ({vendor_str})" if vendor_str else mac_str)

            if "Wi-Fi AP" in proto:
                bg = "#083344" if is_dark else "#e0f2fe"
                fg = colors["accent_cyan"]
                self.proto_badge.setText(f"📶 KABLOSUZ AP ({vendor_str})")
                self.proto_badge.setStyleSheet(f"""
                    background-color: {bg};
                    color: {fg};
                    border: 1px solid {fg};
                    border-radius: 4px;
                    padding: 2px 8px;
                """)
                self.lbl_sw_Diagnostic.setText(
                    f"📶 Kablosuz Erişim Noktası (AP - {vendor_str}) üzerinden bağlantı aktif. Tüm L1-L7, Hız ve İleri Keşif testleri wlan0 üzerinden çalıştırılabilir."
                )
                self.lbl_sw_Diagnostic.setStyleSheet(f"color: {fg}; font-size: 10px; font-weight: bold;")
            elif "L2-ARP" in proto:
                bg = "#451a03" if is_dark else "#fef3c7"
                fg = colors["status_warning"] if is_unauth else colors["accent_cyan"]
                badge_txt = f"✓ SOHO ROUTER / SWITCH ({vendor_str})" if is_unauth else f"✓ {proto} KEŞİF"
                self.proto_badge.setText(badge_txt)
                self.proto_badge.setStyleSheet(f"""
                    background-color: {bg};
                    color: {fg};
                    border: 1px solid {fg};
                    border-radius: 4px;
                    padding: 2px 8px;
                """)
                if is_unauth:
                    self.lbl_sw_Diagnostic.setText(
                        f"ℹ Bağlı cihaz ({vendor_str}) CDP/LLDP yayınlamayan bir yönlendirici/switch. Cihaz bilgileri L2 ARP, MAC OUI ve HTTP/DNS analizi ile keşfedildi. (Kampüs ağında yetkisiz cihaz uyarısı verir.)"
                    )
                else:
                    self.lbl_sw_Diagnostic.setText(
                        f"✓ Ağ geçidi / anahtarlama cihazı ({vendor_str}) L2 ARP ve HTTP/DNS analizi ile keşfedildi (CDP/LLDP kapalı)."
                    )
                self.lbl_sw_Diagnostic.setStyleSheet(f"color: {fg}; font-size: 10px; font-weight: bold;")
            elif is_unauth:
                bg = "#450a0a" if is_dark else "#fee2e2"
                fg = colors["status_error"]
                self.proto_badge.setText(f"⚠ YETKİSİZ SWITCH ({proto})")
                self.proto_badge.setStyleSheet(f"""
                    background-color: {bg};
                    color: {fg};
                    border: 1px solid {fg};
                    border-radius: 4px;
                    padding: 2px 8px;
                """)
                self.lbl_sw_Diagnostic.setText(
                    f"🚨 GÜVENLİK UYARISI: Hatta tüketici tipi / yetkisiz anahtarlama cihazı ({vendor_str}) tespit edildi!"
                )
                self.lbl_sw_Diagnostic.setStyleSheet(f"color: {fg}; font-size: 10px; font-weight: bold;")
            elif nac_active and "CDP" not in proto and "LLDP" not in proto:
                bg = "#451a03" if is_dark else "#fef3c7"
                fg = colors["status_warning"]
                self.proto_badge.setText(f"🔒 {proto}")
                self.proto_badge.setStyleSheet(f"""
                    background-color: {bg};
                    color: {fg};
                    border: 1px solid {fg};
                    border-radius: 4px;
                    padding: 2px 8px;
                """)
                self.lbl_sw_Diagnostic.setText(
                    "🔒 Portta 802.1X NAC / Port-Security aktif. Switch MAC/VLAN yakalandı; arka plan dinleyicisi 60 sn'lik Cisco CDP paketini bekliyor (geldiğinde otomatik güncellenir)."
                )
                self.lbl_sw_Diagnostic.setStyleSheet(f"color: {fg}; font-size: 10px; font-weight: bold;")
            else:
                bg = "#022c22" if is_dark else "#dcfce7"
                fg = colors["status_success"]
                self.proto_badge.setText(f"✓ {proto} AKTİF")
                self.proto_badge.setStyleSheet(f"""
                    background-color: {bg};
                    color: {fg};
                    border: 1px solid {fg};
                    border-radius: 4px;
                    padding: 2px 8px;
                """)
                nac_note = " (802.1X NAC Aktif)" if nac_active else ""
                self.lbl_sw_Diagnostic.setText(
                    f"✓ Kurumsal anahtarlama cihazı ({proto}{nac_note}) doğrulandı. Yetkisiz ara switch/hub bulgusuna rastlanmadı."
                )
                self.lbl_sw_Diagnostic.setStyleSheet(f"color: {fg}; font-size: 10px; font-weight: bold;")
        else:
            gw_mac = d.get("gateway_mac", "")
            vendor = d.get("vendor", "Bilinmiyor")
            bg = "#451a03" if is_dark else "#fef3c7"
            fg = colors["status_warning"]
            self.proto_badge.setText("CDP/LLDP BEKLENİYOR")
            self.proto_badge.setStyleSheet(f"""
                background-color: {bg};
                color: {fg};
                border: 1px solid {fg};
                border-radius: 4px;
                padding: 2px 8px;
            """)
            self.val_sw_name.setText("CDP / LLDP Bekleniyor (Arka Plan Dinlemede)")
            self.val_sw_model.setText(f"Ağ Geçidi Üreticisi: {vendor}")
            self.val_sw_ios.setText("--")
            self.val_sw_mac.setText(gw_mac if gw_mac else "--")
            self.lbl_sw_Diagnostic.setText(
                "⚠ Not: Cisco CDP paketleri 60 saniyede bir yayınlanır. Arka plan dinleyicisi paketi yakaladığında bu ekran otomatik güncellenir."
            )
            self.lbl_sw_Diagnostic.setStyleSheet(f"color: {fg}; font-size: 10px;")

    def _run_arp_sweep(self):
        self.btn_run_arp.setEnabled(False)
        self.btn_run_arp.setText("Alt Ağ Taranıyor...")
        self.lbl_arp_value.setText("Ölçülüyor...")

        real_ip = NetworkDetector.get_ip_address_cidr()
        prefix = "192.168.1."
        if real_ip and "." in real_ip:
            base_ip = real_ip.split("/")[0]
            parts = base_ip.split(".")
            if len(parts) == 4:
                prefix = f"{parts[0]}.{parts[1]}.{parts[2]}."

        self.lbl_subnet_tag.setText(f"Alt Ağ: {prefix}0/24")

        self._arp_worker = BaseWorker(self.arp_scanner.scan_subnet, subnet_prefix=prefix)
        self._arp_worker.signals.result.connect(self._on_arp_finished, Qt.QueuedConnection)
        self._arp_worker.signals.error.connect(self._on_arp_error, Qt.QueuedConnection)
        QThreadPool.globalInstance().start(self._arp_worker)

    def _on_arp_finished(self, devices: list):
        colors = ThemeManager.get_colors()
        self.btn_run_arp.setEnabled(True)
        self.btn_run_arp.setText("IP Doluluk Oranını Ölç")

        active_count = len(devices)
        total_capacity = 254
        pct = (active_count / float(total_capacity)) * 100.0

        self.arp_progress.setValue(min(active_count, total_capacity))
        self.lbl_arp_value.setText(f"%{pct:.1f} Dolu ({active_count} / {total_capacity} Aktif IP)")

        if pct >= 85.0:
            color = colors["status_error"]
        elif pct >= 60.0:
            color = colors["status_warning"]
        else:
            color = colors["status_success"]
        self.lbl_arp_value.setStyleSheet(f"background: transparent; color: {color}; font-weight: 900;")

    def _on_arp_error(self, err_tuple):
        self.btn_run_arp.setEnabled(True)
        self.btn_run_arp.setText("IP Doluluk Oranını Ölç")
        self.lbl_arp_value.setText("Tarama Hatası")
