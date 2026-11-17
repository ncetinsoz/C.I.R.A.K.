"""
Dual-Theme Engine: Dark Industrial (#020617) and Light Industrial (#f8fafc).
Eliminates Qt stylesheet inheritance artifacts and delivers high-contrast industrial ergonomics.
"""

from cirak import config


class ThemeManager:
    """Manages active theme and generates clean, inheritance-safe QSS stylesheets."""

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
        /* Base Window and Container Styles */
        QMainWindow, QWidget#CentralWidget, QStackedWidget {{
            background-color: {colors["bg_main"]};
            color: {colors["text_primary"]};
            font-family: "DejaVu Sans", "Liberation Sans", "Segoe UI", sans-serif;
            font-size: 13px;
        }}

        /* CRITICAL: Explicitly set transparent background and no border on all labels to eliminate box artifacts */
        QLabel {{
            background-color: transparent;
            border: none;
            color: {colors["text_primary"]};
        }}

        /* Top and Bottom Status Bars */
        QFrame#TopBar {{
            background-color: {colors["bar_bg"]};
            border-bottom: 1px solid {colors["bar_border"]};
        }}
        QFrame#BottomBar {{
            background-color: {colors["card_bg"]};
            border: 1px solid {colors["card_border"]};
            border-radius: 8px;
        }}

        /* Buttons */
        QPushButton {{
            background-color: {colors["card_bg"]};
            border: 1px solid {colors["card_border"]};
            border-radius: 6px;
            color: {colors["text_primary"]};
            padding: 5px 12px;
            font-weight: 700;
            font-size: 12px;
        }}
        QPushButton:hover {{
            background-color: {colors["card_hover"]};
            border: 1px solid {colors["accent_cyan"]};
        }}
        QPushButton:pressed {{
            background-color: {colors["accent_cyan"]};
            color: {'#020617' if is_dark else '#ffffff'};
        }}

        QPushButton.PrimaryBtn {{
            background-color: {colors["accent_cyan"]};
            color: {'#020617' if is_dark else '#ffffff'};
            border: none;
            border-radius: 6px;
            font-weight: 800;
            font-size: 12px;
        }}
        QPushButton.PrimaryBtn:hover {{
            background-color: {'#38bdf8' if is_dark else '#0284c7'};
        }}
        QPushButton.PrimaryBtn:pressed {{
            background-color: {'#0891b2' if is_dark else '#0369a1'};
        }}

        /* Badges */
        QLabel.BadgePass {{
            background-color: {'#022c22' if is_dark else '#ecfdf5'};
            color: {colors["status_success"]};
            border: 1px solid {colors["status_success"]};
            border-radius: 4px;
            padding: 2px 6px;
            font-weight: 800;
            font-size: 11px;
            font-family: "DejaVu Sans Mono", "Liberation Mono", monospace;
        }}
        QLabel.BadgeWarning {{
            background-color: {'#451a03' if is_dark else '#fffbeb'};
            color: {colors["status_warning"]};
            border: 1px solid {colors["status_warning"]};
            border-radius: 4px;
            padding: 2px 6px;
            font-weight: 800;
            font-size: 11px;
            font-family: "DejaVu Sans Mono", "Liberation Mono", monospace;
        }}
        QLabel.BadgeFail {{
            background-color: {'#450a0a' if is_dark else '#fef2f2'};
            color: {colors["status_error"]};
            border: 1px solid {colors["status_error"]};
            border-radius: 4px;
            padding: 2px 6px;
            font-weight: 800;
            font-size: 11px;
            font-family: "DejaVu Sans Mono", "Liberation Mono", monospace;
        }}
        QLabel.BadgePending {{
            background-color: transparent;
            color: {colors["text_muted"]};
            border: 1px solid {colors["card_border"]};
            border-radius: 4px;
            padding: 2px 6px;
            font-weight: 700;
            font-size: 11px;
            font-family: "DejaVu Sans Mono", "Liberation Mono", monospace;
        }}

        /* Progress Bar */
        QProgressBar {{
            background-color: {colors["card_bg"]};
            border: 1px solid {colors["card_border"]};
            border-radius: 3px;
            text-align: center;
        }}
        QProgressBar::chunk {{
            background-color: {colors["accent_cyan"]};
            border-radius: 2px;
        }}

        /* Table Widget */
        QTableWidget {{
            background-color: {colors["card_bg"]};
            border: 1px solid {colors["card_border"]};
            gridline-color: {colors["card_border"]};
            color: {colors["text_primary"]};
            border-radius: 8px;
        }}
        QHeaderView::section {{
            background-color: {colors["bar_bg"]};
            color: {colors["text_secondary"]};
            border: 1px solid {colors["card_border"]};
            font-weight: 700;
            padding: 4px;
        }}
        """
