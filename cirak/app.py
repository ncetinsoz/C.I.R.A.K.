"""
Application Entry Point for Ç.I.R.A.K. Handheld Network Analyzer.
Usage:
    python -m cirak.app [--simulate] [--fullscreen] [--no-boot] [--theme dark|light]
"""

import argparse
import logging
import os
import sys
from typing import Optional
from cirak import config, __version__


def run_terminal_diag(interface: Optional[str] = None, simulate: bool = False):
    """Run full L1-L7 diagnostic suite from terminal without launching Qt GUI."""
    from cirak.backend.network_detector import NetworkDetector
    from cirak.backend.autotest import AutoTestRunner

    iface = interface or NetworkDetector.get_active_interface()
    carrier = NetworkDetector.get_carrier(iface)
    speed, duplex = NetworkDetector.get_speed_duplex(iface)
    ip_cidr = NetworkDetector.get_ip_address_cidr(iface) or "IP Yok"
    gw_info = NetworkDetector.get_default_gateway()
    gw_ip = gw_info["gateway"] if gw_info else "Yok"
    dns_servers = NetworkDetector.get_dns_servers()

    print("\n" + "=" * 70)
    print(f"  Ç.I.R.A.K. v{__version__} - Donanım Teşhis ve Ağ Durum Raporu")
    print("=" * 70)
    print(f"  Aktif Port  : {iface} (Carrier: {'UP' if carrier else 'DOWN'}, Link: {speed}M {duplex})")
    print(f"  Atanan IP   : {ip_cidr}")
    print(f"  Ağ Geçidi   : {gw_ip}")
    print(f"  DNS Sunucu  : {', '.join(dns_servers) if dns_servers else 'Yok'}")
    print("-" * 70)
    print("  L1-L7 Test Süiti Koşturuluyor...")

    runner = AutoTestRunner(interface=iface, simulate=simulate)
    report = runner.run_all()

    for s in report.steps:
        status_tag = f"[{s.status.value}]"
        print(f"  {s.name:<24} {status_tag:<10} {s.summary}")
    print("=" * 70)
    res_str = "BAŞARILI ✓" if report.overall_passed else "DİKKAT (Uyarı/Hata) ✗"
    print(f"  Sonuç: {res_str} | Toplam Süre: {report.total_duration_ms:.1f} ms")
    print("=" * 70 + "\n")


def parse_args():
    parser = argparse.ArgumentParser(
        description=f"Ç.I.R.A.K. El Terminali v{__version__} - Ağ Teşhis ve Keşif Cihazı"
    )
    parser.add_argument(
        "--diag",
        action="store_true",
        help="Arayüz açmadan terminalde L1-L7 donanım teşhisi koştur ve sonuç tablosunu yazdır",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        default=False,
        help="Ağ donanımı çağrılarını simülasyon modunda çalıştır (Yalnızca laboratuvar/test ortamı için)",
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

    # CLI Diagnostic mode
    if args.diag:
        run_terminal_diag(simulate=args.simulate)
        return

    # Touch and HiDPI settings
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    # Configure structured logging for systemd / journalctl
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger("cirak")

    from cirak.backend.network_detector import NetworkDetector
    active_iface = NetworkDetector.get_active_interface()
    carrier = NetworkDetector.get_carrier(active_iface)
    ip_cidr = NetworkDetector.get_ip_address_cidr(active_iface) or "Bağlantı Yok"

    logger.info(
        "Ç.I.R.A.K. v%s başlatıldı. [Arayüz: %s | Link: %s | IP: %s | Ekran: 800x480]",
        __version__,
        active_iface,
        "UP" if carrier else "DOWN",
        ip_cidr,
    )

    from PySide6.QtWidgets import QApplication
    from cirak.gui.theme import ThemeManager
    from cirak.gui.main_window import MainWindow
    from cirak.backend.lldp_cdp import LLDPCdpTest
    from cirak.backend.settings_manager import SettingsManager

    # Start continuous L2 background sniffer for 60s Cisco CDP / LLDP / 802.1X NAC frames
    if not args.simulate:
        LLDPCdpTest.ensure_background_listener(active_iface)

    app = QApplication(sys.argv)
    app.setApplicationName("Ç.I.R.A.K.")
    app.setApplicationVersion(__version__)

    # Load saved theme from persistent settings unless --theme was explicitly passed on CLI
    saved_theme = SettingsManager(simulate=args.simulate).settings.theme
    initial_theme = args.theme if "--theme" in sys.argv else (saved_theme or config.THEME_DARK)
    ThemeManager.set_theme(initial_theme)

    window = MainWindow(show_boot=not args.no_boot)

    if args.fullscreen:
        window.showFullScreen()
    else:
        window.show()

    sys.exit(app.exec())



if __name__ == "__main__":
    main()
