"""
Main Window for Ç.I.R.A.K. Handheld Network Analyzer.
Fixed 800x480 resolution layout with QStackedWidget page navigation
and real-time hardware network telemetry polling.
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QStackedWidget,
    QApplication,
)
from cirak import config
from cirak.backend.network_detector import NetworkDetector
from cirak.gui.theme import ThemeManager
from cirak.gui.components.top_bar import TopBar
from cirak.gui.components.bottom_bar import BottomBar
from cirak.gui.views.main_menu import MainMenuView
from cirak.gui.views.autotest_view import AutoTestView
from cirak.gui.views.discovery_view import DiscoveryView
from cirak.gui.views.rogue_dhcp_view import RogueDHCPView
from cirak.gui.views.speed_test_view import SpeedTestView
from cirak.gui.views.wifi_view import WiFiView
from cirak.gui.views.boot_screen import BootScreen


class MainWindow(QMainWindow):
    """800x480 fixed touchscreen main window with live hardware telemetry."""

    def __init__(self, show_boot: bool = True):
        super().__init__()
        self.setWindowTitle("Ç.I.R.A.K. - Çok Amaçlı İnceleme, Raporlama ve Ağ Keşif Cihazı")
        self.setFixedSize(config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
        self.setAttribute(Qt.WA_AcceptTouchEvents, True)

        self._init_ui(show_boot)
        self.apply_theme()

        # Telemetry timer: updates real IP and link carrier every 3 seconds
        self.telemetry_timer = QTimer(self)
        self.telemetry_timer.timeout.connect(self._poll_network_telemetry)
        self.telemetry_timer.start(3000)
        self._poll_network_telemetry()

    def _init_ui(self, show_boot: bool):
        central_widget = QWidget(self)
        central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Top Status Bar (40px)
        self.top_bar = TopBar(self)
        self.top_bar.theme_toggled.connect(self._on_theme_changed)

        # 2. Page Router Stack (398px)
        self.stack = QStackedWidget(self)

        self.boot_screen = BootScreen(self)
        self.main_menu = MainMenuView(self)
        self.autotest_view = AutoTestView(self)
        self.discovery_view = DiscoveryView(self)
        self.rogue_view = RogueDHCPView(self)
        self.speed_view = SpeedTestView(self)
        self.wifi_view = WiFiView(self)

        self.stack.addWidget(self.boot_screen)     # Index 0
        self.stack.addWidget(self.main_menu)       # Index 1
        self.stack.addWidget(self.autotest_view)   # Index 2
        self.stack.addWidget(self.discovery_view)  # Index 3
        self.stack.addWidget(self.rogue_view)      # Index 4
        self.stack.addWidget(self.speed_view)      # Index 5
        self.stack.addWidget(self.wifi_view)       # Index 6

        # Navigation wiring
        self.boot_screen.boot_completed.connect(lambda: self.show_page("main"))
        self.main_menu.navigate_requested.connect(self._on_navigate)
        self.autotest_view.back_requested.connect(lambda: self.show_page("main"))
        self.discovery_view.back_requested.connect(lambda: self.show_page("main"))
        self.rogue_view.back_requested.connect(lambda: self.show_page("main"))
        self.speed_view.back_requested.connect(lambda: self.show_page("main"))
        self.wifi_view.back_requested.connect(lambda: self.show_page("main"))

        # 3. Bottom Quick-Info Bar (42px)
        self.bottom_bar = BottomBar(self)

        main_layout.addWidget(self.top_bar)
        main_layout.addWidget(self.stack)
        main_layout.addWidget(self.bottom_bar)

        if show_boot:
            self.show_page("boot")
            self.top_bar.setVisible(False)
            self.bottom_bar.setVisible(False)
            self.boot_screen.start_boot()
        else:
            self.show_page("main")

    def show_page(self, page_name: str):
        """Navigate to page by name."""
        if page_name == "boot":
            self.stack.setCurrentIndex(0)
            self.top_bar.setVisible(False)
            self.bottom_bar.setVisible(False)
        elif page_name == "main":
            self.top_bar.setVisible(True)
            self.bottom_bar.setVisible(True)
            self.stack.setCurrentIndex(1)
        elif page_name == "autotest":
            self.stack.setCurrentIndex(2)
        elif page_name == "discovery":
            self.stack.setCurrentIndex(3)
        elif page_name == "rogue":
            self.stack.setCurrentIndex(4)
        elif page_name == "speed":
            self.stack.setCurrentIndex(5)
        elif page_name == "wifi":
            self.stack.setCurrentIndex(6)

    def _on_navigate(self, dest: str):
        if dest == "autotest":
            self.show_page("autotest")
        elif dest == "discovery":
            self.show_page("discovery")
        elif dest == "rogue":
            self.show_page("rogue")
        elif dest == "speed":
            self.show_page("speed")
        elif dest == "wifi":
            self.show_page("wifi")
        elif dest == "settings":
            ThemeManager.toggle_theme()
            self.apply_theme()

    def _on_theme_changed(self, theme_name: str):
        self.apply_theme()

    def apply_theme(self):
        """Re-render entire application stylesheet and notify child views."""
        stylesheet = ThemeManager.get_stylesheet()
        QApplication.instance().setStyleSheet(stylesheet)
        self.top_bar.update_logo()
        self.top_bar.update_theme_icon()
        self.boot_screen.update_logo()
        self.main_menu.update_theme()

    def _poll_network_telemetry(self):
        """Poll real network hardware status and update bars."""
        active_iface = NetworkDetector.get_active_interface()
        has_carrier = NetworkDetector.get_carrier(active_iface)
        speed, _ = NetworkDetector.get_speed_duplex(active_iface)

        self.top_bar.update_eth_status(has_carrier, speed)
        self.bottom_bar.refresh_telemetry()
