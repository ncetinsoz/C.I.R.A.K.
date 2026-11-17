"""
Application Entry Point for Ç.I.R.A.K. Handheld Network Analyzer.
Usage:
    python -m cirak.app [--simulate] [--fullscreen] [--no-boot] [--theme dark|light]
"""

import argparse
import os
import sys
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from cirak import config, __version__
from cirak.gui.theme import ThemeManager
from cirak.gui.main_window import MainWindow


def parse_args():
    parser = argparse.ArgumentParser(
        description=f"Ç.I.R.A.K. El Terminali v{__version__} - Ağ Teşhis ve Keşif Cihazı"
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        default=True,
        help="Ağ donanımı çağrılarını simülasyon modunda çalıştır (Geliştirme/Laboratuvar ortamı)",
    )
    parser.add_argument(
        "--fullscreen",
        action="store_true",
        help="Ekranı tam ekran (800x480 kiosk) modunda başlat",
    )
    parser.add_argument(
        "--no-boot",
        action="store_true",
        help="Açılış (Splash) animasyonunu atlayarak doğrudan ana menüye geç",
    )
    parser.add_argument(
        "--theme",
        choices=["dark", "light"],
        default="dark",
        help="Başlangıç arayüz teması (Varsayılan: dark)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Touch and HiDPI settings
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    app = QApplication(sys.argv)
    app.setApplicationName("Ç.I.R.A.K.")
    app.setApplicationVersion(__version__)

    # Set theme
    ThemeManager.set_theme(args.theme)

    window = MainWindow(show_boot=not args.no_boot)

    if args.fullscreen:
        window.showFullScreen()
    else:
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
