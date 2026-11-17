"""
Configuration parameters for Ç.I.R.A.K. Handheld Network Analyzer.
Target Hardware: Raspberry Pi 4 Model B + Official 7" Touchscreen (800x480).
"""

from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"
IMAGES_DIR = ASSETS_DIR / "images"
DOCS_DIR = BASE_DIR / "docs"

LOGO_LIGHT_PATH = IMAGES_DIR / "cirak_logo_light.jpg"
LOGO_DARK_PATH = IMAGES_DIR / "cirak_logo_dark.jpg"

# Display & Layout Specifications (800x480 Fixed Touch Resolution)
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 480
TOP_BAR_HEIGHT = 40
BOTTOM_BAR_HEIGHT = 42
CONTENT_HEIGHT = SCREEN_HEIGHT - TOP_BAR_HEIGHT - BOTTOM_BAR_HEIGHT  # 398 px

# Touch Target Dimensions (2 rows x 3 columns)
MENU_BUTTON_WIDTH = 240
MENU_BUTTON_HEIGHT = 160

# Network Defaults
DEFAULT_ETH_INTERFACE = "eth0"
DEFAULT_WLAN_INTERFACE = "wlan0"
DEFAULT_TIMEOUT_SEC = 5.0

# Active Profile Defaults
DEFAULT_PROFILE = "Kampus-Dinamik-DHCP"
DEFAULT_DNS_TARGET = "kampus.edu.tr"
DEFAULT_EXTERNAL_URL = "http://ulakbim.tubitak.gov.tr"
FALLBACK_EXTERNAL_URL = "http://www.google.com"

# Approved DHCP Servers (Whitelist for Rogue Detection)
APPROVED_DHCP_SERVERS = [
    "10.20.0.1",       # Central Campus DHCP 1
    "10.20.0.2",       # Central Campus DHCP 2
    "192.168.1.1",     # Lab Gateway (optional)
]

# Dual Theme Palette Definitions
THEME_DARK = "dark"
THEME_LIGHT = "light"

COLORS = {
    "dark": {
        "bg_main": "#020617",         # Deep Obsidian Black
        "card_bg": "#0f172a",         # Navy Dark Blue
        "card_border": "#334155",     # Slate Border
        "card_hover": "#1e293b",      # Hover slate
        "text_primary": "#ffffff",    # Crisp White
        "text_secondary": "#94a3b8",  # Muted Slate
        "accent_cyan": "#22d3ee",     # Tech Cyan
        "accent_amber": "#f59e0b",    # Amber / Orange
        "status_success": "#10b981",  # Emerald Green
        "status_error": "#ef4444",    # Vibrant Red
        "status_warning": "#eab308",  # Yellow Warning
        "bar_bg": "#0b1329",          # Top/Bottom bar bg
        "bar_border": "#1e293b",
    },
    "light": {
        "bg_main": "#f8fafc",         # Clean Slate White
        "card_bg": "#ffffff",         # Pure White
        "card_border": "#cbd5e1",     # Light Border
        "card_hover": "#f1f5f9",      # Light Hover
        "text_primary": "#0f172a",    # Dark Slate
        "text_secondary": "#475569",  # Charcoal Muted
        "accent_cyan": "#0284c7",     # Deep Cyan
        "accent_amber": "#b45309",    # Deep Amber
        "status_success": "#059669",  # Forest Emerald
        "status_error": "#dc2626",    # Deep Red
        "status_warning": "#ca8a04",  # Deep Yellow
        "bar_bg": "#ffffff",          # Top/Bottom bar bg
        "bar_border": "#e2e8f0",
    }
}
