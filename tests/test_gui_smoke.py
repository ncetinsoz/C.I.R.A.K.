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

    # Check page stack
    assert window.stack.count() == 5
    assert window.stack.currentWidget() == window.main_menu

    # Test navigation
    window.show_page("autotest")
    assert window.stack.currentWidget() == window.autotest_view

    window.show_page("discovery")
    assert window.stack.currentWidget() == window.discovery_view

    window.show_page("rogue")
    assert window.stack.currentWidget() == window.rogue_view

    window.show_page("main")
    assert window.stack.currentWidget() == window.main_menu


def test_theme_toggle_smoke(qapp):
    window = MainWindow(show_boot=False)
    initial_theme = ThemeManager.get_current_theme()

    # Toggle
    new_theme = ThemeManager.toggle_theme()
    assert new_theme != initial_theme
    window.apply_theme()

    # Toggle back
    restored_theme = ThemeManager.toggle_theme()
    assert restored_theme == initial_theme
    window.apply_theme()
