"""
Bottom Quick-Info Bar (38 px height) for Ç.I.R.A.K. Handheld.
Displays real-time hardware discovery state (CDP / LLDP / 802.1X NAC) and clean IPv4 address.
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
from cirak.backend.lldp_cdp import LLDPCdpTest
from cirak.gui.theme import ThemeManager


class BottomBar(QFrame):
    """Fixed 38px bottom quick-info bar with live network telemetry."""

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("BottomBar")
        self.setFixedHeight(config.BOTTOM_BAR_HEIGHT)
        self._init_ui()
        self.update_theme()
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

        self.lbl_disc_val = QLabel("Dinleniyor (CDP / LLDP bekleniyor...)")
        self.lbl_disc_val.setFont(disc_font)

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

        self.lbl_ip_val = QLabel("Bağlantı Yok")
        self.lbl_ip_val.setFont(ip_font)

        right_box.addWidget(self.lbl_ip_title)
        right_box.addWidget(self.lbl_ip_val)

        layout.addLayout(right_box)

    def update_theme(self):
        """Update bottom bar colors for Dark and Light themes."""
        colors = ThemeManager.get_colors()
        self.lbl_disc_title.setStyleSheet(f"background: transparent; color: {colors['text_muted']}; font-weight: bold;")
        self.lbl_ip_title.setStyleSheet(f"background: transparent; color: {colors['text_muted']}; font-weight: bold;")
        self.refresh_telemetry()

    def refresh_telemetry(self):
        """Query real network hardware and background L2 sniffer cache to update IP and switch discovery."""
        is_dark = ThemeManager.get_current_theme() == config.THEME_DARK
        colors = ThemeManager.get_colors()
        active_iface = NetworkDetector.get_active_interface()
        has_carrier = NetworkDetector.get_carrier(active_iface)
        real_ip = NetworkDetector.get_ip_address_cidr(active_iface)

        # Update IP (Clean IP without /24 CIDR mask on bottom bar)
        if real_ip:
            clean_ip = real_ip.split("/")[0]
            self.lbl_ip_val.setText(clean_ip)
            self.lbl_ip_val.setStyleSheet(f"background: transparent; color: {colors['status_success']}; font-weight: 800;")
        elif has_carrier:
            self.lbl_ip_val.setText("DHCP / NAC Bekleniyor...")
            self.lbl_ip_val.setStyleSheet(f"background: transparent; color: {colors['status_warning']}; font-weight: 700;")
        else:
            self.lbl_ip_val.setText(f"{active_iface}: Link Yok")
            self.lbl_ip_val.setStyleSheet(f"background: transparent; color: {colors['status_error']}; font-weight: 700;")

        # Update Switch / CDP / LLDP / NAC discovery from daemon OR background L2 sniffer cache
        lldp = NetworkDetector.get_lldp_from_daemon(active_iface)
        if not (lldp and lldp.get("system_name")):
            bg_cached = LLDPCdpTest.get_cached_discovery(active_iface, max_age_sec=180.0)
            if bg_cached and (bg_cached.get("system_name") or bg_cached.get("port_id")):
                lldp = bg_cached

        disc_accent = "#38bdf8" if is_dark else "#0369a1"
        if lldp and (lldp.get("system_name") or lldp.get("port_id")):
            proto = lldp.get("protocol", "CDP/LLDP")
            sw_name = lldp.get("system_name", "Switch")
            port_str = f" • {lldp.get('port_id')}" if lldp.get("port_id") else ""
            vlan_str = f" • VLAN {lldp['vlan_id']}" if lldp.get("vlan_id") else ""
            self.lbl_disc_val.setText(f"[{proto}] {sw_name}{port_str}{vlan_str}")
            self.lbl_disc_val.setStyleSheet(f"background: transparent; color: {disc_accent}; font-weight: 700;")
        else:
            self.lbl_disc_val.setText("Dinleniyor (CDP / LLDP bekleniyor...)")
            self.lbl_disc_val.setStyleSheet(f"background: transparent; color: {colors['text_secondary']};")

    def set_discovery_info(self, text: str):
        self.lbl_disc_val.setText(text)

    def set_ip_info(self, text: str):
        colors = ThemeManager.get_colors()
        clean_ip = text.split("/")[0] if "/" in text else text
        self.lbl_ip_val.setText(clean_ip)
        self.lbl_ip_val.setStyleSheet(f"background: transparent; color: {colors['status_success']}; font-weight: 800;")
