"""
Bottom Quick-Info Bar (38 px height) for Ç.I.R.A.K. Handheld.
Displays real-time hardware discovery state and actual assigned IPv4/CIDR address.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QWidget,
)
from cirak import config
from cirak.backend.network_detector import NetworkDetector
from cirak.gui.theme import ThemeManager


class BottomBar(QFrame):
    """Fixed 38px bottom quick-info bar with live network telemetry."""

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("BottomBar")
        self.setFixedHeight(config.BOTTOM_BAR_HEIGHT)
        self._init_ui()
        self.refresh_telemetry()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(8)

        # 1. Left Section: Switch Discovery
        left_box = QHBoxLayout()
        left_box.setContentsMargins(0, 0, 0, 0)
        left_box.setSpacing(4)

        self.lbl_disc_title = QLabel("Son Keşif:")
        disc_font = QFont("DejaVu Sans Mono", 9)
        self.lbl_disc_title.setFont(disc_font)
        self.lbl_disc_title.setStyleSheet("background: transparent; color: #64748b;")

        self.lbl_disc_val = QLabel("Dinleniyor (CDP / LLDP bekleniyor...)")
        self.lbl_disc_val.setFont(disc_font)
        self.lbl_disc_val.setStyleSheet("background: transparent; color: #38bdf8; font-weight: 700;")

        left_box.addWidget(self.lbl_disc_title)
        left_box.addWidget(self.lbl_disc_val)

        layout.addLayout(left_box)
        layout.addStretch()

        # 2. Right Section: Real IP (Clean IPv4 without CIDR mask)
        right_box = QHBoxLayout()
        right_box.setContentsMargins(0, 0, 0, 0)
        right_box.setSpacing(4)

        self.lbl_ip_title = QLabel("IP:")
        ip_font = QFont("DejaVu Sans Mono", 9, QFont.Bold)
        self.lbl_ip_title.setFont(ip_font)
        self.lbl_ip_title.setStyleSheet("background: transparent; color: #64748b;")

        self.lbl_ip_val = QLabel("Bağlantı Yok")
        self.lbl_ip_val.setFont(ip_font)
        self.lbl_ip_val.setStyleSheet("background: transparent; color: #ef4444; font-weight: 700;")

        right_box.addWidget(self.lbl_ip_title)
        right_box.addWidget(self.lbl_ip_val)

        layout.addLayout(right_box)

    def refresh_telemetry(self):
        """Query real network hardware and update displayed IP and discovery text."""
        active_iface = NetworkDetector.get_active_interface()
        has_carrier = NetworkDetector.get_carrier(active_iface)
        real_ip = NetworkDetector.get_ip_address_cidr(active_iface)

        # Update IP (Clean IP without /24 CIDR mask on bottom bar)
        if real_ip:
            clean_ip = real_ip.split("/")[0]
            self.lbl_ip_val.setText(clean_ip)
            self.lbl_ip_val.setStyleSheet("background: transparent; color: #10b981; font-weight: 800;")
        elif has_carrier:
            self.lbl_ip_val.setText("DHCP Bekleniyor...")
            self.lbl_ip_val.setStyleSheet("background: transparent; color: #f59e0b; font-weight: 700;")
        else:
            self.lbl_ip_val.setText(f"{active_iface}: Link Yok")
            self.lbl_ip_val.setStyleSheet("background: transparent; color: #ef4444; font-weight: 700;")

        # Update Switch / CDP / LLDP discovery
        lldp = NetworkDetector.get_lldp_from_daemon(active_iface)
        if lldp and lldp.get("system_name"):
            proto = lldp.get("protocol", "CDP/LLDP")
            vlan_str = f" • VLAN {lldp['vlan_id']}" if lldp.get("vlan_id") else ""
            self.lbl_disc_val.setText(f"[{proto}] {lldp['system_name']} • {lldp.get('port_id')}{vlan_str}")
            self.lbl_disc_val.setStyleSheet("background: transparent; color: #38bdf8; font-weight: 700;")
        else:
            self.lbl_disc_val.setText("Dinleniyor (CDP / LLDP bekleniyor...)")
            self.lbl_disc_val.setStyleSheet("background: transparent; color: #94a3b8;")

    def set_discovery_info(self, text: str):
        self.lbl_disc_val.setText(text)

    def set_ip_info(self, text: str):
        clean_ip = text.split("/")[0] if "/" in text else text
        self.lbl_ip_val.setText(clean_ip)
        self.lbl_ip_val.setStyleSheet("background: transparent; color: #10b981; font-weight: 800;")
