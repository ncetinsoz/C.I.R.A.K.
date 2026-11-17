"""
Network Discovery & Diagnostic View:
1. Switch, Port & VLAN (LLDP/CDP)
2. Switch Port LED Flasher (Port Blinker)
3. Subnet ARP IP Occupancy Sweep
"""

from PySide6.QtCore import Qt, Signal, QThreadPool
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QFrame,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)
from cirak.backend.lldp_cdp import LLDPCdpTest
from cirak.backend.port_blinker import PortBlinker
from cirak.backend.arp_scanner import ARPScanner
from cirak.core.models import ARPDevice
from cirak.core.worker import BaseWorker


class DiscoveryView(QWidget):
    """Network discovery tools view."""

    back_requested = Signal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.blinker = PortBlinker(simulate=True)
        self.arp_scanner = ARPScanner(simulate=True)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 10, 14, 10)
        main_layout.setSpacing(8)

        # Header
        header = QHBoxLayout()
        self.back_btn = QPushButton("← Geri")
        self.back_btn.setFixedSize(70, 30)
        self.back_btn.clicked.connect(self.back_requested.emit)

        title = QLabel("Ağ Keşfi & Teşhis Araçları")
        title.setStyleSheet("font-size: 13px; font-weight: 800; color: #22d3ee;")

        header.addWidget(self.back_btn)
        header.addWidget(title)
        header.addStretch()

        # Tools Row (3 tool cards)
        tools_layout = QHBoxLayout()
        tools_layout.setSpacing(10)

        # Tool 1: LLDP/CDP
        self.card_lldp = QFrame()
        self.card_lldp.setProperty("class", "StatusCard")
        l1 = QVBoxLayout(self.card_lldp)
        l1.setContentsMargins(10, 8, 10, 8)
        lbl_t1 = QLabel("🔍 Switch, Port & VLAN")
        lbl_t1.setStyleSheet("font-weight: 800; color: #22d3ee; font-size: 11px;")
        self.lldp_details = QLabel("Switch: Catalyst-9300\nPort: Gi1/0/24 | VLAN: 102\nYönetim IP: 10.20.0.254")
        self.lldp_details.setStyleSheet("font-family: monospace; font-size: 10px; color: #94a3b8;")
        self.btn_read_lldp = QPushButton("LLDP Paketlerini Dinle")
        self.btn_read_lldp.setFixedHeight(26)
        self.btn_read_lldp.clicked.connect(self._run_lldp_query)
        l1.addWidget(lbl_t1)
        l1.addWidget(self.lldp_details)
        l1.addStretch()
        l1.addWidget(self.btn_read_lldp)

        # Tool 2: Port Blinker (LED Flares)
        self.card_blink = QFrame()
        self.card_blink.setProperty("class", "StatusCard")
        l2 = QVBoxLayout(self.card_blink)
        l2.setContentsMargins(10, 8, 10, 8)
        lbl_t2 = QLabel("💡 Port Işıkları (Flaşör)")
        lbl_t2.setStyleSheet("font-weight: 800; color: #f59e0b; font-size: 11px;")
        self.blink_status = QLabel("Switch port LED'ini 2 Hz frekansla yakıp söndürerek kabinet takibini sağlar.")
        self.blink_status.setWordWrap(True)
        self.blink_status.setStyleSheet("font-size: 10px; color: #94a3b8;")
        self.btn_toggle_blink = QPushButton("Flaşörü Başlat (Blink)")
        self.btn_toggle_blink.setFixedHeight(26)
        self.btn_toggle_blink.clicked.connect(self._toggle_blinker)
        l2.addWidget(lbl_t2)
        l2.addWidget(self.blink_status)
        l2.addStretch()
        l2.addWidget(self.btn_toggle_blink)

        # Tool 3: ARP Sweep Trigger
        self.card_arp = QFrame()
        self.card_arp.setProperty("class", "StatusCard")
        l3 = QVBoxLayout(self.card_arp)
        l3.setContentsMargins(10, 8, 10, 8)
        lbl_t3 = QLabel("📊 Alt Ağ IP Doluluk (ARP)")
        lbl_t3.setStyleSheet("font-weight: 800; color: #10b981; font-size: 11px;")
        self.arp_summary = QLabel("10.20.102.0/24 alt ağındaki aktif cihazları ve MAC adreslerini listeler.")
        self.arp_summary.setWordWrap(True)
        self.arp_summary.setStyleSheet("font-size: 10px; color: #94a3b8;")
        self.btn_run_arp = QPushButton("Hızlı ARP Taraması")
        self.btn_run_arp.setProperty("class", "PrimaryBtn")
        self.btn_run_arp.setFixedHeight(26)
        self.btn_run_arp.clicked.connect(self._run_arp_sweep)
        l3.addWidget(lbl_t3)
        l3.addWidget(self.arp_summary)
        l3.addStretch()
        l3.addWidget(self.btn_run_arp)

        tools_layout.addWidget(self.card_lldp)
        tools_layout.addWidget(self.card_blink)
        tools_layout.addWidget(self.card_arp)

        # Host Table
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["IP Adresi", "MAC Adresi", "Cihaz / Üretici", "RTT (ms)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setFixedHeight(160)

        main_layout.addLayout(header)
        main_layout.addLayout(tools_layout)
        main_layout.addWidget(self.table)

    def _run_lldp_query(self):
        test = LLDPCdpTest(simulate=True)
        res = test.run()
        d = res.details
        self.lldp_details.setText(
            f"Switch: {d.get('system_name', 'Bilinmiyor')}\n"
            f"Port: {d.get('port_id', 'Bilinmiyor')} | VLAN: {d.get('vlan_id', 'Bilinmiyor')}\n"
            f"Yönetim IP: {d.get('management_ip', 'Bilinmiyor')}"
        )

    def _toggle_blinker(self):
        if self.blinker.is_blinking:
            self.blinker.stop_blink()
            self.btn_toggle_blink.setText("Flaşörü Başlat (Blink)")
            self.blink_status.setText("Flaşör durduruldu.")
        else:
            self.btn_toggle_blink.setText("Flaşörü Durdur [YANIP SÖNÜYOR]")
            self.blink_status.setText("Switch port LED'i şu anda yanıp sönüyor (2 Hz)...")
            self.blinker.start_blink(duration_sec=20)

    def _run_arp_sweep(self):
        self.btn_run_arp.setEnabled(False)
        self.btn_run_arp.setText("Taranıyor...")
        self.table.setRowCount(0)

        worker = BaseWorker(self.arp_scanner.scan_subnet)
        worker.signals.result.connect(self._on_arp_finished)
        QThreadPool.globalInstance().start(worker)

    def _on_arp_finished(self, devices):
        self.btn_run_arp.setEnabled(True)
        self.btn_run_arp.setText("Hızlı ARP Taraması")
        self.table.setRowCount(len(devices))
        for row, dev in enumerate(devices):
            self.table.setItem(row, 0, QTableWidgetItem(dev.ip))
            self.table.setItem(row, 1, QTableWidgetItem(dev.mac))
            self.table.setItem(row, 2, QTableWidgetItem(dev.vendor))
            self.table.setItem(row, 3, QTableWidgetItem(f"{dev.response_time_ms:.1f}"))
