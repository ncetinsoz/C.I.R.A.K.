"""
PySide6 Offscreen Smoke Test for Ç.I.R.A.K. 800x480 GUI.
"""

import os
import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from cirak import config
from cirak.gui.main_window import MainWindow
from cirak.gui.theme import ThemeManager


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_main_window_initialization(qapp):
    window = MainWindow(show_boot=False)

    # Resolution check (800x480 fixed)
    assert window.width() == 800
    assert window.height() == 480
    assert window.top_bar.height() == 40
    assert window.bottom_bar.height() == 42

    # Check page stack (boot, main, autotest, discovery, rogue, speed, wifi, settings)
    assert window.stack.count() == 8
    assert window.stack.currentWidget() == window.main_menu

    # Test navigation
    window.show_page("autotest")
    assert window.stack.currentWidget() == window.autotest_view

    window.show_page("discovery")
    assert window.stack.currentWidget() == window.discovery_view

    window.show_page("rogue")
    assert window.stack.currentWidget() == window.rogue_view

    window.show_page("speed")
    assert window.stack.currentWidget() == window.speed_view

    window.show_page("wifi")
    assert window.stack.currentWidget() == window.wifi_view

    window.show_page("settings")
    assert window.stack.currentWidget() == window.settings_view

    window.show_page("main")
    assert window.stack.currentWidget() == window.main_menu


def test_theme_toggle_smoke(qapp):
    ThemeManager.set_theme(config.THEME_DARK)
    window = MainWindow(show_boot=False)
    assert ThemeManager.get_current_theme() == config.THEME_DARK
    assert "#0f172a" in window.discovery_view.switch_panel.styleSheet()

    # Toggle to Light Mode and verify all inner views update their stylesheets
    new_theme = ThemeManager.toggle_theme()
    assert new_theme == config.THEME_LIGHT
    window.apply_theme()
    assert "#e2e8f0" in window.discovery_view.switch_panel.styleSheet()
    assert "#e2e8f0" in window.settings_view.card_ip.styleSheet()

    # Toggle back to Dark Mode
    restored_theme = ThemeManager.toggle_theme()
    assert restored_theme == config.THEME_DARK
    window.apply_theme()
    assert "#0f172a" in window.discovery_view.switch_panel.styleSheet()
    assert window.top_bar.power_btn is not None

