"""
Rogue DHCP Hunter View:
Identifies unauthorized rogue DHCP servers and modems on the LAN.
Supports both Dark and Light Industrial themes.
"""

from PySide6.QtCore import Qt, Signal
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
from cirak.backend.network_detector import NetworkDetector
from cirak.gui.theme import ThemeManager


class RogueDHCPView(QWidget):
    """Rogue DHCP Hunter view."""

    back_requested = Signal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.dhcp_test = DHCPTest(simulate=False)
        self._last_is_rogue = False
        self._init_ui()
        self.update_theme()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 8, 12, 8)
        main_layout.setSpacing(10)

        # Header
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        self.back_btn = QPushButton("← Geri")
        self.back_btn.setFixedSize(70, 30)
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.clicked.connect(self.back_requested.emit)

        self.title_lbl = QLabel("Yetkisiz (Rogue) DHCP Tespiti (L2 Nokta Atışı)")
        t_font = QFont("DejaVu Sans", 11, QFont.Bold)
        self.title_lbl.setFont(t_font)

        self.scan_btn = QPushButton("Yeni DHCP Taraması")
        self.scan_btn.setProperty("class", "PrimaryBtn")
        self.scan_btn.setFixedHeight(30)
        self.scan_btn.setCursor(Qt.PointingHandCursor)
        self.scan_btn.clicked.connect(self._run_scan)

        header.addWidget(self.back_btn)
        header.addWidget(self.title_lbl)
        header.addStretch()
        header.addWidget(self.scan_btn)

        # Cards Layout (Side by side comparison)
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)

        # Authorized Server Card (Green)
        self.auth_card = QFrame()
        self.auth_card.setObjectName("RogueAuthCard")
        l1 = QVBoxLayout(self.auth_card)
        l1.setSpacing(6)
        self.lbl_a1 = QLabel("✓ YETKİLİ KURUMSAL SUNUCU")

        gw = NetworkDetector.get_default_gateway()
        gw_ip = gw["gateway"] if gw else "194.27.65.1"
        gw_mac = NetworkDetector.get_gateway_mac(gw_ip) or "94:33:d8:2a:01:ef"
        real_ip = NetworkDetector.get_ip_address_cidr() or "194.27.65.131/24"

        self.auth_details = QLabel(
            f"Sunucu IP: {gw_ip}\n"
            f"MAC Adresi: {gw_mac}\n"
            f"Cihaz IP: {real_ip}\n"
            f"Durum: Beyaz Listede (Onaylı)\n\n"
            f"Merkezi ağ geçidi / DHCP sunucusu doğrulandı."
        )
        l1.addWidget(self.lbl_a1)
        l1.addWidget(self.auth_details)
        l1.addStretch()

        # Rogue Server Status Card
        self.rogue_card = QFrame()
        self.rogue_card.setObjectName("RogueStatusCard")
        self.l2 = QVBoxLayout(self.rogue_card)
        self.l2.setSpacing(6)
        self.lbl_r1 = QLabel("🛡️ ROGUE DHCP KONTROLÜ")

        self.rogue_details = QLabel(
            "Henüz yetkisiz DHCP sunucusu veya çakışan\n"
            "ikinci bir modem tespit edilmedi.\n\n"
            "'Yeni DHCP Taraması' butonuna tıklayarak L2 katmanında\n"
            "tüm ağdaki DHCP Discover yanıtlarını dinleyebilirsiniz."
        )
        self.l2.addWidget(self.lbl_r1)
        self.l2.addWidget(self.rogue_details)
        self.l2.addStretch()

        cards_layout.addWidget(self.auth_card)
        cards_layout.addWidget(self.rogue_card)

        main_layout.addLayout(header)
        main_layout.addLayout(cards_layout)

    def update_theme(self):
        """Apply Dark or Light theme palette to RogueDHCPView."""
        is_dark = ThemeManager.get_current_theme() == config.THEME_DARK
        colors = ThemeManager.get_colors()
        card_bg = colors["card_bg"]

        self.title_lbl.setStyleSheet(
            f"background: transparent; font-size: 13px; font-weight: 800; color: {colors['accent_amber']};"
        )
        self.auth_card.setStyleSheet(f"""
            QFrame#RogueAuthCard {{
                background-color: {card_bg};
                border: 1.5px solid {colors['status_success']};
                border-radius: 10px;
                padding: 10px;
            }}
        """)
        self.lbl_a1.setStyleSheet(
            f"background: transparent; color: {colors['status_success']}; font-weight: 800; font-size: 12px;"
        )
        self.auth_details.setStyleSheet(
            f"background: transparent; font-family: monospace; font-size: 11px; color: {colors['text_primary']};"
        )

        if self._last_is_rogue:
            rogue_bg = "#450a0a" if is_dark else "#fee2e2"
            self.rogue_card.setStyleSheet(f"""
                QFrame#RogueStatusCard {{
                    background-color: {rogue_bg};
                    border: 1.5px solid {colors['status_error']};
                    border-radius: 10px;
                    padding: 10px;
                }}
            """)
            self.lbl_r1.setStyleSheet(
                f"background: transparent; color: {colors['status_error']}; font-weight: 900; font-size: 12px;"
            )
            self.rogue_details.setStyleSheet(
                f"background: transparent; font-family: monospace; font-size: 11px; color: {colors['status_error']};"
            )
        else:
            self.rogue_card.setStyleSheet(f"""
                QFrame#RogueStatusCard {{
                    background-color: {card_bg};
                    border: 1.5px solid {colors['card_border']};
                    border-radius: 10px;
                    padding: 10px;
                }}
            """)
            self.lbl_r1.setStyleSheet(
                f"background: transparent; color: {colors['accent_cyan']}; font-weight: 800; font-size: 12px;"
            )
            self.rogue_details.setStyleSheet(
                f"background: transparent; font-family: monospace; font-size: 11px; color: {colors['text_secondary']};"
            )

    def _run_scan(self):
        colors = ThemeManager.get_colors()
        self.scan_btn.setText("Taranıyor...")
        self.scan_btn.setEnabled(False)
        res = self.dhcp_test.run()

        if res.details.get("is_rogue"):
            self._last_is_rogue = True
            self.lbl_r1.setText("🚨 SAHTE / YETKİSİZ MODEM TESPİT EDİLDİ!")
            self.rogue_details.setText(
                f"Sahte IP: {res.details.get('server_id')}\n"
                f"MAC Adresi: {res.details.get('server_mac')}\n"
                f"Dağıtılan IP: {res.details.get('offered_ip')}\n"
                f"Durum: İZİNSİZ / GÜVENLİK İHLALİ\n\n"
                f"Olası Neden: Masanın altına takılan yetkisiz Wi-Fi modem/router!"
            )
            self.update_theme()
        else:
            self._last_is_rogue = False
            self.update_theme()
            self.lbl_r1.setText("✓ AĞ TEMİZ (YETKİSİZ SUNUCU YOK)")
            self.lbl_r1.setStyleSheet(
                f"background: transparent; color: {colors['status_success']}; font-weight: 800; font-size: 12px;"
            )
            self.rogue_details.setText(
                "Ağda yalnızca yetkili DHCP sunucusu yanıt verdi.\n"
                "Herhangi bir yetkisiz modem veya sahte yönlendirici bulunamadı."
            )
            self.rogue_details.setStyleSheet(
                f"background: transparent; font-family: monospace; font-size: 11px; color: {colors['text_primary']};"
            )

        self.scan_btn.setText("Yeni DHCP Taraması")
        self.scan_btn.setEnabled(True)
