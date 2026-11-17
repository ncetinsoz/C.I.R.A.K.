"""
Dual-Theme Engine: Dark Industrial and Light Industrial palettes and QSS stylesheets.
Optimized for 7" 800x480 capacitive touch screen.
"""

from cirak import config


class ThemeManager:
    """Manages active theme and generates PySide6 QSS stylesheets."""

    _current_theme = config.THEME_DARK

    @classmethod
    def get_current_theme(cls) -> str:
        return cls._current_theme

    @classmethod
    def set_theme(cls, theme_name: str):
        if theme_name in (config.THEME_DARK, config.THEME_LIGHT):
            cls._current_theme = theme_name

    @classmethod
    def toggle_theme(cls) -> str:
        cls._current_theme = (
            config.THEME_LIGHT if cls._current_theme == config.THEME_DARK else config.THEME_DARK
        )
        return cls._current_theme

    @classmethod
    def get_colors(cls) -> dict:
        return config.COLORS[cls._current_theme]

    @classmethod
    def get_stylesheet(cls) -> str:
        colors = cls.get_colors()
        is_dark = cls._current_theme == config.THEME_DARK

        return f"""
        QWidget {{
            background-color: {colors["bg_main"]};
            color: {colors["text_primary"]};
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            font-size: 13px;
        }}

        /* Top & Bottom Status Bars */
        QFrame#TopBar, QFrame#BottomBar {{
            background-color: {colors["bar_bg"]};
            border-bottom: 1px solid {colors["bar_border"]};
            border-top: 1px solid {colors["bar_border"]};
        }}

        /* Main Menu Touch Cards (240x160 px) */
        QFrame.MenuCard {{
            background-color: {colors["card_bg"]};
            border: 1px solid {colors["card_border"]};
            border-radius: 10px;
        }}
        QFrame.MenuCard:hover {{
            background-color: {colors["card_hover"]};
            border: 1.5px solid {colors["accent_cyan"]};
        }}

        /* AutoTest & Detail Cards */
        QFrame.StatusCard {{
            background-color: {colors["card_bg"]};
            border: 1px solid {colors["card_border"]};
            border-radius: 8px;
        }}

        /* Standard Buttons */
        QPushButton {{
            background-color: {colors["card_bg"]};
            border: 1px solid {colors["card_border"]};
            border-radius: 6px;
            color: {colors["text_primary"]};
            padding: 6px 12px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: {colors["card_hover"]};
            border: 1px solid {colors["accent_cyan"]};
        }}
        QPushButton:pressed {{
            background-color: {colors["accent_cyan"]};
            color: #020617;
        }}

        /* Primary Action Buttons */
        QPushButton.PrimaryBtn {{
            background-color: {colors["accent_cyan"]};
            color: {'#020617' if is_dark else '#ffffff'};
            border: none;
            border-radius: 6px;
            font-weight: 800;
        }}
        QPushButton.PrimaryBtn:hover {{
            background-color: {'#38bdf8' if is_dark else '#0369a1'};
        }}

        /* Danger / Alert Badges */
        QLabel.BadgeDanger {{
            background-color: #450a0a;
            color: #f87171;
            border: 1px solid #991b1b;
            border-radius: 4px;
            padding: 2px 6px;
            font-weight: bold;
        }}

        /* Success Badges */
        QLabel.BadgeSuccess {{
            background-color: {'#022c22' if is_dark else '#ecfdf5'};
            color: {colors["status_success"]};
            border: 1px solid {colors["status_success"]};
            border-radius: 4px;
            padding: 2px 6px;
            font-weight: bold;
        }}

        /* Progress Bar */
        QProgressBar {{
            background-color: {colors["card_bg"]};
            border: 1px solid {colors["card_border"]};
            border-radius: 4px;
            text-align: center;
            color: {colors["text_primary"]};
        }}
        QProgressBar::chunk {{
            background-color: {colors["accent_cyan"]};
            border-radius: 3px;
        }}

        /* Scrollbars */
        QScrollBar:vertical {{
            border: none;
            background: {colors["bg_main"]};
            width: 8px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: {colors["card_border"]};
            min-height: 20px;
            border-radius: 4px;
        }}

        /* Table Widget */
        QTableWidget {{
            background-color: {colors["card_bg"]};
            border: 1px solid {colors["card_border"]};
            gridline-color: {colors["card_border"]};
            selection-background-color: {colors["card_hover"]};
        }}
        QHeaderView::section {{
            background-color: {colors["bar_bg"]};
            color: {colors["text_secondary"]};
            border: 1px solid {colors["card_border"]};
            font-weight: bold;
            padding: 4px;
        }}
        """
