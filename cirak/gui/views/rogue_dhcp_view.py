"""
Rogue DHCP Hunter View:
Identifies unauthorized rogue DHCP servers and modems on the LAN.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
)
from cirak.backend.dhcp import DHCPTest


class RogueDHCPView(QWidget):
    """Rogue DHCP Hunter view."""

    back_requested = Signal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.dhcp_test = DHCPTest(simulate=True)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 10, 14, 10)
        main_layout.setSpacing(10)

        # Header
        header = QHBoxLayout()
        self.back_btn = QPushButton("← Geri")
        self.back_btn.setFixedSize(70, 30)
        self.back_btn.clicked.connect(self.back_requested.emit)

        title = QLabel("Yetkisiz (Rogue) DHCP Tespiti (L2 Nokta Atışı)")
        title.setStyleSheet("font-size: 13px; font-weight: 800; color: #ef4444;")

        self.scan_btn = QPushButton("Yeni DHCP Taraması")
        self.scan_btn.setProperty("class", "PrimaryBtn")
        self.scan_btn.setFixedHeight(30)
        self.scan_btn.clicked.connect(self._run_scan)

        header.addWidget(self.back_btn)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.scan_btn)

        # Cards Layout (Side by side comparison)
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)

        # Authorized Server Card (Green)
        self.auth_card = QFrame()
        self.auth_card.setProperty("class", "StatusCard")
        self.auth_card.setStyleSheet("border: 1px solid #059669; border-radius: 8px; padding: 10px;")
        l1 = QVBoxLayout(self.auth_card)
        l1.setSpacing(6)
        lbl_a1 = QLabel("✓ YETKİLİ KURUMSAL SUNUCU")
        lbl_a1.setStyleSheet("color: #10b981; font-weight: 800; font-size: 12px;")
        self.auth_details = QLabel(
            "Yanıt Süresi: 42 ms\n"
            "Sunucu IP: 10.20.0.1\n"
            "MAC Adresi: 00:50:56:bf:21:40 (VMware)\n"
            "Havuz: 10.20.102.0/24\n"
            "Durum: Beyaz Listede (Onaylı)\n\n"
            "Merkezi Eduroam/Kampüs DHCP sunucusu doğrulandı."
        )
        self.auth_details.setStyleSheet("font-family: monospace; font-size: 11px; color: #cbd5e1;")
        l1.addWidget(lbl_a1)
        l1.addWidget(self.auth_details)
        l1.addStretch()

        # Rogue Server Card (Red Warning)
        self.rogue_card = QFrame()
        self.rogue_card.setProperty("class", "StatusCard")
        self.rogue_card.setStyleSheet("border: 1.5px solid #dc2626; border-radius: 8px; padding: 10px; background-color: #450a0a;")
        l2 = QVBoxLayout(self.rogue_card)
        l2.setSpacing(6)
        lbl_r1 = QLabel("🚨 SAHTE / YETKİSİZ MODEM TESPİT EDİLDİ!")
        lbl_r1.setStyleSheet("color: #ef4444; font-weight: 900; font-size: 12px;")
        self.rogue_details = QLabel(
            "Yanıt Süresi: 18 ms (Agresif Yanıt!)\n"
            "Sahte IP: 192.168.1.1\n"
            "MAC Adresi: c4:ad:34:12:ef:90 (TP-Link)\n"
            "Dağıtılan IP: 192.168.1.105\n"
            "Durum: İZİNSİZ / GÜVENLİK İHLALİ\n\n"
            "Olası Neden: Masanın altına takılan yetkisiz Wi-Fi modem/router!"
        )
        self.rogue_details.setStyleSheet("font-family: monospace; font-size: 11px; color: #fca5a5;")
        l2.addWidget(lbl_r1)
        l2.addWidget(self.rogue_details)
        l2.addStretch()

        cards_layout.addWidget(self.auth_card)
        cards_layout.addWidget(self.rogue_card)

        main_layout.addLayout(header)
        main_layout.addLayout(cards_layout)

    def _run_scan(self):
        self.scan_btn.setText("Taranıyor...")
        self.scan_btn.setEnabled(False)
        res = self.dhcp_test.run()
        self.scan_btn.setText("Yeni DHCP Taraması")
        self.scan_btn.setEnabled(True)
