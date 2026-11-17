"""
Configuration parameters for Ç.I.R.A.K. Handheld Network Analyzer.
Target Hardware: Raspberry Pi 4 Model B + Official 7" Touchscreen (800x480).
"""

from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"
IMAGES_DIR = ASSETS_DIR / "images"
DOCS_DIR = BASE_DIR / "docs"

# Official Logos
LOGO_PATH = IMAGES_DIR / "cirak_logo.png"
LOGO_LIGHT_PATH = IMAGES_DIR / "cirak_logo.png"
LOGO_DARK_PATH = IMAGES_DIR / "cirak_logo_dark.jpg"

# Display & Layout Specifications (800x480 Fixed Touch Resolution)
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 480
TOP_BAR_HEIGHT = 40
BOTTOM_BAR_HEIGHT = 42
CONTENT_HEIGHT = SCREEN_HEIGHT - TOP_BAR_HEIGHT - BOTTOM_BAR_HEIGHT  # 398 px

# Touch Target Dimensions (2 rows x 3 columns)
MENU_BUTTON_WIDTH = 240
MENU_BUTTON_HEIGHT = 156

# Network Defaults
DEFAULT_ETH_INTERFACE = "eth0"
DEFAULT_WLAN_INTERFACE = "wlan0"
DEFAULT_TIMEOUT_SEC = 4.0

# Active Profile Defaults
DEFAULT_PROFILE = "Kampus-Dinamik-DHCP"
DEFAULT_DNS_TARGET = "google.com"
FALLBACK_DNS_TARGET = "kampus.edu.tr"
DEFAULT_EXTERNAL_URL = "http://connectivitycheck.gstatic.com/generate_204"
ULAKBIM_EXTERNAL_URL = "http://ulakbim.tubitak.gov.tr"

# Approved DHCP Servers (Whitelist for Rogue Detection)
APPROVED_DHCP_SERVERS = [
    "10.20.0.1",       # Central Campus DHCP 1
    "10.20.0.2",       # Central Campus DHCP 2
    "192.168.1.1",     # Lab Gateway 1
    "192.168.1.254",   # Lab Gateway 2
    "192.168.0.1",     # Lab Gateway 3
]

# Dual Theme Palette Definitions (Faithful to cirak_ui_prototype.html & Tailwind Dark Industrial)
THEME_DARK = "dark"
THEME_LIGHT = "light"

COLORS = {
    "dark": {
        "bg_main": "#020617",         # Slate-950 / Deep Obsidian Black
        "card_bg": "#0f172a",         # Slate-900
        "card_border": "#1e293b",     # Slate-800
        "card_hover": "#1e293b",      # Hover slate
        "text_primary": "#f8fafc",    # Crisp Slate White
        "text_secondary": "#94a3b8",  # Muted Slate
        "text_muted": "#64748b",      # Slate 500
        "accent_cyan": "#06b6d4",     # Cyan 500
        "accent_indigo": "#6366f1",   # Indigo 500
        "accent_amber": "#f59e0b",    # Amber 500
        "accent_emerald": "#10b981",  # Emerald 500
        "accent_sky": "#0ea5e9",      # Sky 500
        "accent_slate": "#64748b",    # Slate 500
        "status_success": "#10b981",  # Emerald Green
        "status_error": "#ef4444",    # Vibrant Red
        "status_warning": "#f59e0b",  # Amber Warning
        "bar_bg": "#020617",          # Top/Bottom bar background
        "bar_border": "#1e293b",
    },
    "light": {
        "bg_main": "#f8fafc",         # Clean Slate White
        "card_bg": "#ffffff",         # Pure White
        "card_border": "#cbd5e1",     # Light Border
        "card_hover": "#f1f5f9",      # Light Hover
        "text_primary": "#0f172a",    # Dark Slate
        "text_secondary": "#475569",  # Charcoal Muted
        "text_muted": "#94a3b8",
        "accent_cyan": "#0284c7",     # Deep Cyan
        "accent_indigo": "#4f46e5",   # Deep Indigo
        "accent_amber": "#b45309",    # Deep Amber
        "accent_emerald": "#059669",  # Forest Emerald
        "accent_sky": "#0284c7",      # Sky Blue
        "accent_slate": "#475569",    # Slate
        "status_success": "#059669",  # Forest Emerald
        "status_error": "#dc2626",    # Deep Red
        "status_warning": "#ca8a04",  # Deep Yellow
        "bar_bg": "#ffffff",          # Top/Bottom bar background
        "bar_border": "#e2e8f0",
    }
}
