from __future__ import annotations

from collections.abc import Callable

from getpass_app.models.preferences import UiPreferences
from getpass_core import config


class SettingsService:
    def __init__(
        self,
        load: Callable[[], dict] = config.load_settings,
        save: Callable[[dict], bool] = config.save_settings,
    ) -> None:
        self._load = load
        self._save = save

    def load_ui_preferences(self) -> UiPreferences:
        theme = self._load().get("theme", "light")
        if theme not in ("light", "dark"):
            theme = "light"
        return UiPreferences(theme=theme)

    def save_theme(self, theme: str) -> bool:
        if theme not in ("light", "dark"):
            raise ValueError(f"Unsupported theme: {theme}")
        return self._save({"theme": theme})
