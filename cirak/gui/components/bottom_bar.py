"""
Bottom Quick-Info Bar (42 px height) for Ç.I.R.A.K. Handheld.
Displays switch/port discovery status and active IP address.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QWidget,
)
from cirak import config


class BottomBar(QFrame):
    """Fixed 42px bottom quick-info bar."""

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("BottomBar")
        self.setFixedHeight(config.BOTTOM_BAR_HEIGHT)
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(10)

        # Left: Discovery Summary
        self.discovery_label = QLabel("Son Keşif: SW-KAT2-KENAR03 • Port: Gi1/0/24 (VLAN 102)")
        self.discovery_label.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 500;")

        layout.addWidget(self.discovery_label)
        layout.addStretch()

        # Right: Active IP address
        self.ip_label = QLabel("IP: 10.20.102.88/24")
        self.ip_label.setStyleSheet("color: #22d3ee; font-family: monospace; font-size: 11px; font-weight: bold;")

        layout.addWidget(self.ip_label)

    def set_discovery_info(self, switch_name: str, port_id: str, vlan_id: str):
        """Update switch discovery text."""
        self.discovery_label.setText(f"Son Keşif: {switch_name} • Port: {port_id} (VLAN {vlan_id})")

    def set_ip_info(self, ip_str: str):
        """Update active IP text."""
        self.ip_label.setText(f"IP: {ip_str}")
