"""
Network Discovery & Switch Diagnostic View:
1. Top-Left: Subnet IP Occupancy Rate (% and Active/254 count with progress bar)
2. Top-Right: Switch Port LED Flasher with Fluke-style Cadence Slider (Cisco err-disable safe)
3. Bottom Full-Width Panel: Connected Network Switch (CDP / LLDP / STP / Unauthorized Switch Inspector)
"""

from typing import Optional
from PySide6.QtCore import Qt, Signal, QThreadPool
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
from cirak.backend.lldp_cdp import LLDPCdpTest
from cirak.backend.port_blinker import PortBlinker
from cirak.backend.arp_scanner import ARPScanner
from cirak.backend.network_detector import NetworkDetector
from cirak.core.models import TestResult, TestStatus
from cirak.core.worker import BaseWorker


class DiscoveryView(QWidget):
    """Network discovery and switch inspection view optimized for 7-inch 800x480 touchscreen."""

    back_requested = Signal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.blinker = PortBlinker(simulate=False)
        self.arp_scanner = ARPScanner(simulate=False)
        self._lldp_worker: Optional[BaseWorker] = None
        self._arp_worker: Optional[BaseWorker] = None
        self._init_ui()

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

        title = QLabel("Ağ Keşfi & Anahtarlama Cihazı (Switch) Analizi")
        t_font = QFont("DejaVu Sans", 11, QFont.Bold)
        title.setFont(t_font)
        title.setStyleSheet("background: transparent; color: #818cf8; font-weight: 800;")

        header.addWidget(self.back_btn)
        header.addWidget(title)
        header.addStretch()

        # =========================================================
        # 2. Top Row: 2 Compact Cards (IP Occupancy % & Port Blinker Slider)
        # =========================================================
        top_cards_layout = QHBoxLayout()
        top_cards_layout.setSpacing(10)

        # --- Card 1: IP Doluluk Oranı (ARP Occupancy) ---
        self.card_arp = QFrame()
        self.card_arp.setObjectName("DiscoveryTopCard")
        self.card_arp.setStyleSheet("""
            QFrame#DiscoveryTopCard {
                background-color: #0f172a;
                border: 1.5px solid #10b981;
                border-radius: 10px;
            }
            QFrame#DiscoveryTopCard QLabel {
                background: transparent;
                border: none;
            }
        """)
        l_arp = QVBoxLayout(self.card_arp)
        l_arp.setContentsMargins(12, 8, 12, 8)
        l_arp.setSpacing(4)

        arp_hdr = QHBoxLayout()
        lbl_arp_title = QLabel("📊 IP Doluluk Oranı")
        lbl_arp_title.setStyleSheet("font-weight: 800; color: #34d399; font-size: 11px;")
        self.lbl_subnet_tag = QLabel("Alt Ağ: /24")
        self.lbl_subnet_tag.setStyleSheet("font-family: monospace; font-size: 10px; color: #94a3b8;")
        arp_hdr.addWidget(lbl_arp_title)
        arp_hdr.addStretch()
        arp_hdr.addWidget(self.lbl_subnet_tag)

        self.lbl_arp_value = QLabel("-- % (-- / 254 Aktif IP)")
        val_font = QFont("DejaVu Sans Mono", 13, QFont.Bold)
        self.lbl_arp_value.setFont(val_font)
        self.lbl_arp_value.setStyleSheet("color: #f8fafc; font-weight: 900;")

        self.arp_progress = QProgressBar()
        self.arp_progress.setFixedHeight(6)
        self.arp_progress.setRange(0, 254)
        self.arp_progress.setValue(0)
        self.arp_progress.setTextVisible(False)
        self.arp_progress.setStyleSheet("""
            QProgressBar {
                background-color: #1e293b;
                border: none;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background-color: #10b981;
                border-radius: 3px;
            }
        """)

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
        self.card_blink.setStyleSheet("""
            QFrame#DiscoveryBlinkCard {
                background-color: #0f172a;
                border: 1.5px solid #a855f7;
                border-radius: 10px;
            }
            QFrame#DiscoveryBlinkCard QLabel {
                background: transparent;
                border: none;
            }
        """)
        l_blink = QVBoxLayout(self.card_blink)
        l_blink.setContentsMargins(12, 8, 12, 8)
        l_blink.setSpacing(4)

        blink_hdr = QHBoxLayout()
        lbl_blink_title = QLabel("💡 Port Işıkları (Flaşör)")
        lbl_blink_title.setStyleSheet("font-weight: 800; color: #c084fc; font-size: 11px;")
        self.lbl_blink_rate = QLabel("Periyot: 4.0 sn (Cisco Güvenli)")
        self.lbl_blink_rate.setStyleSheet("font-family: monospace; font-size: 10px; color: #e9d5ff;")
        blink_hdr.addWidget(lbl_blink_title)
        blink_hdr.addStretch()
        blink_hdr.addWidget(self.lbl_blink_rate)

        # Slider: 10 to 50 (representing 1.0s to 5.0s interval)
        # Note: Cisco default link-flap errdisable triggers at 5 flaps per 10s (<2.0s period)
        slider_row = QHBoxLayout()
        lbl_fast = QLabel("Hızlı (1s)")
        lbl_fast.setStyleSheet("font-size: 9px; color: #f59e0b;")
        self.blink_slider = QSlider(Qt.Horizontal)
        self.blink_slider.setRange(10, 50)
        self.blink_slider.setValue(40)  # Default 4.0s (100% safe against Cisco link-flap err-disable)
        self.blink_slider.setFixedHeight(20)
        self.blink_slider.valueChanged.connect(self._on_slider_changed)
        lbl_safe = QLabel("Güvenli (5s)")
        lbl_safe.setStyleSheet("font-size: 9px; color: #10b981;")

        slider_row.addWidget(lbl_fast)
        slider_row.addWidget(self.blink_slider)
        slider_row.addWidget(lbl_safe)

        self.blink_status = QLabel("Cisco portlarının kapanmaması (err-disable) için ≥3 sn önerilir.")
        self.blink_status.setStyleSheet("font-size: 9px; color: #94a3b8;")

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
        self.switch_panel.setStyleSheet("""
            QFrame#SwitchInspectorPanel {
                background-color: #0f172a;
                border: 1.5px solid #6366f1;
                border-radius: 12px;
            }
            QFrame#SwitchInspectorPanel QLabel {
                background: transparent;
                border: none;
            }
        """)
        sw_layout = QVBoxLayout(self.switch_panel)
        sw_layout.setContentsMargins(14, 10, 14, 10)
        sw_layout.setSpacing(6)

        # Switch Panel Header
        sw_hdr = QHBoxLayout()
        lbl_sw_title = QLabel("🔍 BAĞLI AĞ ANAHTARLAMA CİHAZI (SWITCH)")
        lbl_sw_title.setStyleSheet("font-weight: 900; color: #818cf8; font-size: 12px;")

        self.proto_badge = QLabel("DİNLENİYOR")
        self.proto_badge.setFont(QFont("DejaVu Sans Mono", 9, QFont.Bold))
        self.proto_badge.setStyleSheet("""
            background-color: rgba(99, 102, 241, 0.15);
            color: #a5b4fc;
            border: 1px solid #6366f1;
            border-radius: 4px;
            padding: 2px 8px;
        """)

        self.btn_read_lldp = QPushButton("🔍 CDP / LLDP Paketlerini Dinle")
        self.btn_read_lldp.setProperty("class", "PrimaryBtn")
        self.btn_read_lldp.setFixedHeight(28)
        self.btn_read_lldp.setCursor(Qt.PointingHandCursor)
        self.btn_read_lldp.clicked.connect(self._run_lldp_query)

        sw_hdr.addWidget(lbl_sw_title)
        sw_hdr.addStretch()
        sw_hdr.addWidget(self.proto_badge)
        sw_hdr.addWidget(self.btn_read_lldp)
        sw_layout.addLayout(sw_hdr)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet("background-color: #1e293b; max-height: 1px;")
        sw_layout.addWidget(div)

        # 2-Column Telemetry Grid inside Switch Box
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(6)
        grid.setContentsMargins(2, 4, 2, 4)

        label_style = "color: #64748b; font-size: 11px; font-weight: 700;"
        val_style = "color: #f8fafc; font-family: 'DejaVu Sans Mono', monospace; font-size: 12px; font-weight: 800;"

        # Left Column: Switch Name, Model/Platform, Management IP
        lbl_k_name = QLabel("Cihaz Adı (Switch):")
        lbl_k_name.setStyleSheet(label_style)
        self.val_sw_name = QLabel("Bekleniyor...")
        self.val_sw_name.setStyleSheet("color: #38bdf8; font-family: 'DejaVu Sans Mono', monospace; font-size: 12px; font-weight: 900;")

        lbl_k_model = QLabel("Marka / Model:")
        lbl_k_model.setStyleSheet(label_style)
        self.val_sw_model = QLabel("--")
        self.val_sw_model.setStyleSheet(val_style)

        lbl_k_mgmt = QLabel("Yönetim IP Adresi:")
        lbl_k_mgmt.setStyleSheet(label_style)
        self.val_sw_mgmt = QLabel("--")
        self.val_sw_mgmt.setStyleSheet(val_style)

        # Right Column: Port ID, VLAN ID, MAC & Vendor
        lbl_k_port = QLabel("Bağlı Port (Port ID):")
        lbl_k_port.setStyleSheet(label_style)
        self.val_sw_port = QLabel("--")
        self.val_sw_port.setStyleSheet("color: #10b981; font-family: 'DejaVu Sans Mono', monospace; font-size: 12px; font-weight: 900;")

        lbl_k_vlan = QLabel("VLAN (Native / Tag):")
        lbl_k_vlan.setStyleSheet(label_style)
        self.val_sw_vlan = QLabel("--")
        self.val_sw_vlan.setStyleSheet("color: #f59e0b; font-family: 'DejaVu Sans Mono', monospace; font-size: 12px; font-weight: 900;")

        lbl_k_mac = QLabel("Switch MAC / Üretici:")
        lbl_k_mac.setStyleSheet(label_style)
        self.val_sw_mac = QLabel("--")
        self.val_sw_mac.setStyleSheet(val_style)

        grid.addWidget(lbl_k_name, 0, 0)
        grid.addWidget(self.val_sw_name, 0, 1)
        grid.addWidget(lbl_k_port, 0, 2)
        grid.addWidget(self.val_sw_port, 0, 3)

        grid.addWidget(lbl_k_model, 1, 0)
        grid.addWidget(self.val_sw_model, 1, 1)
        grid.addWidget(lbl_k_vlan, 1, 2)
        grid.addWidget(self.val_sw_vlan, 1, 3)

        grid.addWidget(lbl_k_mgmt, 2, 0)
        grid.addWidget(self.val_sw_mgmt, 2, 1)
        grid.addWidget(lbl_k_mac, 2, 2)
        grid.addWidget(self.val_sw_mac, 2, 3)

        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        sw_layout.addLayout(grid)

        # Security / Diagnostic Note Banner at bottom of Switch Panel
        self.lbl_sw_Diagnostic = QLabel(
            "💡 Bilgi: Cisco CDP (60 sn) ve IEEE LLDP (30 sn) çerçeveleri ile STP BPDU ve yetkisiz switch MAC analizini birlikte yürütür."
        )
        self.lbl_sw_Diagnostic.setWordWrap(True)
        self.lbl_sw_Diagnostic.setStyleSheet("color: #94a3b8; font-size: 10px; font-family: monospace;")
        sw_layout.addStretch()
        sw_layout.addWidget(self.lbl_sw_Diagnostic)

        main_layout.addLayout(header)
        main_layout.addLayout(top_cards_layout, 2)
        main_layout.addWidget(self.switch_panel, 3)

        # Populate initial passive data if daemon already cached CDP/LLDP
        self._refresh_cached_switch_info()

    def _on_slider_changed(self, value: int):
        sec = value / 10.0
        self.blinker.set_interval(sec)
        if sec >= 3.0:
            tag = "Cisco Güvenli"
            color = "#10b981"
        elif sec >= 2.0:
            tag = "Normal"
            color = "#e9d5ff"
        else:
            tag = "Hızlı - Dikkat!"
            color = "#f59e0b"
        self.lbl_blink_rate.setText(f"Periyot: {sec:.1f} sn ({tag})")
        self.lbl_blink_rate.setStyleSheet(f"background: transparent; font-family: monospace; font-size: 10px; color: {color}; font-weight: bold;")

    def _toggle_blinker(self):
        if self.blinker.is_blinking:
            self.blinker.stop_blink()
            self.btn_toggle_blink.setText("Flaşörü Başlat (Blink)")
            self.blink_status.setText("Flaşör durduruldu.")
            self.blink_status.setStyleSheet("background: transparent; font-size: 9px; color: #94a3b8;")
        else:
            sec = self.blink_slider.value() / 10.0
            self.btn_toggle_blink.setText("⏹ Flaşörü Durdur [AKTİF]")
            self.blink_status.setText(f"Port LED {sec:.1f} sn periyotla güvenli şekilde yanıp sönüyor...")
            self.blink_status.setStyleSheet("background: transparent; font-size: 9px; color: #c084fc; font-weight: bold;")
            self.blinker.start_blink(duration_sec=30, interval_sec=sec)

    def _refresh_cached_switch_info(self):
        """Immediately check lldpd cache without blocking UI."""
        cached = NetworkDetector.get_lldp_from_daemon()
        if cached and cached.get("system_name"):
            self._populate_switch_panel(cached)

    def _run_lldp_query(self):
        """Run active CDP/LLDP/L2 capture on background worker thread."""
        self.btn_read_lldp.setText("Dinleniyor (CDP/LLDP)...")
        self.btn_read_lldp.setEnabled(False)
        self.proto_badge.setText("PAKET BEKLENİYOR")

        def _task():
            # Listen for up to 5 seconds on raw socket if daemon doesn't have it yet
            test = LLDPCdpTest(timeout_sec=5.0, simulate=False)
            return test.run()

        self._lldp_worker = BaseWorker(_task)
        self._lldp_worker.signals.result.connect(self._on_lldp_finished, Qt.QueuedConnection)
        self._lldp_worker.signals.error.connect(self._on_lldp_error, Qt.QueuedConnection)
        QThreadPool.globalInstance().start(self._lldp_worker)

    def _on_lldp_finished(self, res: TestResult):
        self.btn_read_lldp.setText("🔍 CDP / LLDP Paketlerini Dinle")
        self.btn_read_lldp.setEnabled(True)
        self._populate_switch_panel(res.details)

    def _on_lldp_error(self, err_tuple):
        self.btn_read_lldp.setText("🔍 CDP / LLDP Paketlerini Dinle")
        self.btn_read_lldp.setEnabled(True)
        self.proto_badge.setText("HATA")

    def _populate_switch_panel(self, d: dict):
        if d.get("system_name") or d.get("port_id"):
            proto = d.get("protocol", "CDP/LLDP")
            is_unauth = d.get("is_unauthorized_switch", False)

            self.val_sw_name.setText(str(d.get("system_name") or "Tespit Edildi"))
            model_str = d.get("system_description") or d.get("vendor") or "Kurumsal Switch"
            self.val_sw_model.setText(str(model_str)[:36])
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
            vendor_str = str(d.get("vendor") or "")
            self.val_sw_mac.setText(f"{mac_str} ({vendor_str})" if vendor_str else mac_str)

            if is_unauth:
                self.proto_badge.setText(f"⚠ YETKİSİZ SWITCH ({proto})")
                self.proto_badge.setStyleSheet("""
                    background-color: #450a0a;
                    color: #ef4444;
                    border: 1px solid #ef4444;
                    border-radius: 4px;
                    padding: 2px 8px;
                """)
                self.lbl_sw_Diagnostic.setText(
                    f"🚨 GÜVENLİK UYARISI: Hatta tüketici tipi / yetkisiz anahtarlama cihazı ({vendor_str}) tespit edildi!"
                )
                self.lbl_sw_Diagnostic.setStyleSheet("color: #ef4444; font-size: 10px; font-weight: bold;")
            else:
                self.proto_badge.setText(f"✓ {proto} AKTİF")
                self.proto_badge.setStyleSheet("""
                    background-color: #022c22;
                    color: #10b981;
                    border: 1px solid #10b981;
                    border-radius: 4px;
                    padding: 2px 8px;
                """)
                self.lbl_sw_Diagnostic.setText(
                    f"✓ Kurumsal anahtarlama cihazı ({proto}) doğrulandı. Yetkisiz ara switch/hub bulgusuna rastlanmadı."
                )
                self.lbl_sw_Diagnostic.setStyleSheet("color: #10b981; font-size: 10px; font-weight: bold;")
        else:
            gw_mac = d.get("gateway_mac", "")
            vendor = d.get("vendor", "Bilinmiyor")
            self.proto_badge.setText("CDP/LLDP BEKLENİYOR")
            self.proto_badge.setStyleSheet("""
                background-color: #451a03;
                color: #f59e0b;
                border: 1px solid #f59e0b;
                border-radius: 4px;
                padding: 2px 8px;
            """)
            self.val_sw_name.setText("CDP / LLDP Yanıtı Alınamadı")
            self.val_sw_model.setText(f"Ağ Geçidi Üreticisi: {vendor}")
            self.val_sw_mac.setText(gw_mac if gw_mac else "--")
            self.lbl_sw_Diagnostic.setText(
                "⚠ Not: Cisco CDP paketleri 60 saniyede bir yayınlanır. Portta yönetimsiz (unmanaged) switch olabilir veya 60 sn içinde tekrar dinleyin."
            )
            self.lbl_sw_Diagnostic.setStyleSheet("color: #f59e0b; font-size: 10px;")

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
        self.btn_run_arp.setEnabled(True)
        self.btn_run_arp.setText("IP Doluluk Oranını Ölç")

        active_count = len(devices)
        total_capacity = 254
        pct = (active_count / float(total_capacity)) * 100.0

        self.arp_progress.setValue(min(active_count, total_capacity))
        self.lbl_arp_value.setText(f"%{pct:.1f} Dolu ({active_count} / {total_capacity} Aktif IP)")

        if pct >= 85.0:
            color = "#ef4444"
        elif pct >= 60.0:
            color = "#f59e0b"
        else:
            color = "#10b981"
        self.lbl_arp_value.setStyleSheet(f"background: transparent; color: {color}; font-weight: 900;")

    def _on_arp_error(self, err_tuple):
        self.btn_run_arp.setEnabled(True)
        self.btn_run_arp.setText("IP Doluluk Oranını Ölç")
        self.lbl_arp_value.setText("Tarama Hatası")
