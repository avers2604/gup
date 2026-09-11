from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from getpass_app.services.settings_service import SettingsService
from getpass_qt.theme.stylesheet import build_stylesheet


class ThemeManager(QObject):
    theme_changed = Signal(str)

    def __init__(self, app: QApplication, settings: SettingsService) -> None:
        super().__init__()
        self._app = app
        self._settings = settings
        self.current_theme = "light"

    def load(self) -> str:
        theme = self._settings.load_ui_preferences().theme
        self.apply(theme, persist=False)
        return theme

    def apply(self, theme: str, *, persist: bool = True) -> None:
        self._app.setStyleSheet(build_stylesheet(theme))
        self.current_theme = theme
        if persist:
            self._settings.save_theme(theme)
        self.theme_changed.emit(theme)

    def toggle(self) -> None:
        self.apply("dark" if self.current_theme == "light" else "light")
