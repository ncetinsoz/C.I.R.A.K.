"""
Pure Vector SVG Icon Library for Ç.I.R.A.K. Handheld Network Analyzer.
Renders crisp, resolution-independent vector icons without relying on system emoji fonts.
"""

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# SVG Vector path templates matching cirak_ui_prototype.html
SVG_ICONS = {
    # 1. Otomatik Test: Lightning / Zap
    "lightning": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M13 10V3L4 14h7v7l9-11h-7z"/>
    </svg>""",

    # 2. Ağ Keşfi: Network Topology / Compass
    "discovery": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"/>
    </svg>""",

    # 3. Yetkisiz DHCP: Shield Alert
    "shield_alert": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
    </svg>""",

    # 4. Hız Testi: Speedometer / Gauge
    "speedometer": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
    </svg>""",

    # 5. Kablosuz Ağ: Wi-Fi Waves
    "wifi": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M8.111 16.404a5.5 5.5 0 017.778 0M12 20h.01m-7.08-7.071c3.904-3.905 10.236-3.905 14.14 0M1.394 9.393c5.857-5.857 15.355-5.857 21.213 0"/>
    </svg>""",

    # 6. Ayarlar & Tema: Sliders / Settings
    "settings": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"/>
    </svg>""",

    # Top Bar: Wikimedia Standard 3-Node Ethernet LAN Port Icon
    "ethernet_port": """<svg viewBox="0 0 800 800" fill="{color}">
        <g transform="translate(0,800) scale(0.1,-0.1)">
            <path d="M2910 6080 l0 -1240 585 0 585 0 0 -325 0 -325 -1955 0 -1955 0 0 -165 0 -165 850 0 850 0 -2 -347 -3 -348 -627 -3 -628 -2 0 -1240 0 -1240 1418 2 1417 3 3 1238 2 1237 -565 0 -565 0 0 350 0 350 2015 0 2015 0 0 -330 0 -330 -640 0 -640 0 0 -1245 0 -1245 1420 0 1420 0 -2 1243 -3 1242 -552 3 -553 2 0 330 0 330 515 0 515 0 0 165 0 165 -1650 0 -1650 0 2 323 3 322 608 3 607 2 -2 1238 -3 1237 -1417 3 -1418 2 0 -1240z m2390 -5 l0 -795 -975 0 -975 0 0 795 0 795 975 0 975 0 0 -795z m2160 -4120 l0 -795 -975 0 -975 0 0 795 0 795 975 0 975 0 0 -795z m-4460 -30 l0 -795 -975 0 -975 0 0 795 0 795 975 0 975 0 0 -795z"/>
        </g>
    </svg>""",

    # Top Bar: Power Bolt
    "power_bolt": """<svg viewBox="0 0 20 20" fill="{color}">
        <path fill-rule="evenodd" d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z" clip-rule="evenodd"/>
    </svg>""",

    # Navigation: Arrow Left (Back)
    "arrow_left": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M15 19l-7-7 7-7"/>
    </svg>""",

    # Theme Toggle: Moon / Sun
    "theme_toggle": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
    </svg>""",

    # Status: Check / Pass
    "check": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
        <path d="M5 13l4 4L19 7"/>
    </svg>""",

    # Switch Port Blinker: Lightbulb
    "bulb": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
    </svg>""",

    # Switch / Network Ports
    "switch": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/>
    </svg>""",

    # Safe Power Off / Shutdown Icon
    "power_off": """<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
        <path d="M18.36 6.64a9 9 0 1 1-12.73 0"/>
        <line x1="12" y1="2" x2="12" y2="12"/>
    </svg>""",
}


def get_svg_pixmap(name: str, color: str = "#22d3ee", size: int = 24) -> QPixmap:
    """Render a crisp, transparent vector SVG icon into a QPixmap."""
    template = SVG_ICONS.get(name)
    if not template:
        # Fallback empty transparent pixmap
        pix = QPixmap(size, size)
        pix.fill(QColor(0, 0, 0, 0))
        return pix

    svg_data = template.format(color=color)
    renderer = QSvgRenderer(QByteArray(svg_data.encode("utf-8")))

    pix = QPixmap(QSize(size, size))
    pix.fill(QColor(0, 0, 0, 0))  # Full transparency
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing, True)
    renderer.render(painter)
    painter.end()

    return pix
