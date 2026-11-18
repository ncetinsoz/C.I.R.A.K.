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

# Active Profile & System Defaults
DEFAULT_PROFILE = "Kampus-Dinamik-DHCP"
DEFAULT_DNS_TARGET = "google.com"
FALLBACK_DNS_TARGET = "deu.edu.tr"
DEFAULT_EXTERNAL_URL = "http://www.google.com"
INTERNAL_CAMPUS_URL = "http://www.deu.edu.tr"
DEFAULT_NTP_SERVER = "time.deu.edu.tr"
SETTINGS_FILE = Path.home() / ".config" / "cirak" / "settings.json"

# Approved DHCP Servers (Whitelist for Rogue Detection)
APPROVED_DHCP_SERVERS = [
    "194.27.65.1",     # DEU Subnet Gateway / DHCP
    "193.140.151.224", # DEU Core DHCP/DNS 1
    "193.140.151.9",   # DEU Core DHCP/DNS 2
    "10.20.0.1",       # Central Campus DHCP 1
    "10.20.0.2",       # Central Campus DHCP 2
]

# Dual Theme Palette Definitions (Default: Dark Industrial)
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
        "bg_main": "#cbd5e1",         # Soft Slate-300 (Non-glare industrial grey)
        "card_bg": "#e2e8f0",         # Soft Slate-200 (Zero pure-white eye strain)
        "card_border": "#94a3b8",     # Muted Slate-400 border
        "card_hover": "#cbd5e1",      # Soft Hover
        "text_primary": "#0f172a",    # Dark Slate-900
        "text_secondary": "#334155",  # Slate-700
        "text_muted": "#475569",      # Slate-600
        "accent_cyan": "#0369a1",     # Deep Ocean Blue
        "accent_indigo": "#4338ca",   # Deep Indigo
        "accent_amber": "#b45309",    # Deep Amber
        "accent_emerald": "#047857",  # Deep Emerald
        "accent_sky": "#0369a1",      # Deep Sky
        "accent_slate": "#334155",    # Slate
        "status_success": "#047857",  # Forest Emerald
        "status_error": "#b91c1c",    # Deep Red
        "status_warning": "#b45309",  # Deep Amber
        "bar_bg": "#94a3b8",          # Soft Slate Top/Bottom bar
        "bar_border": "#64748b",
    }
}
