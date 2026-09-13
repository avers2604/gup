from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict

from getpass_app.models.preferences import OperatorDefaults, UiPreferences
from getpass_core import config

_PRINT_MODES = frozenset({"a4", "a5"})
_BADGE_PRINT_MODES = frozenset({"card", "a4_grid", "a4_single"})
_PREVIEW_TARGETS = frozenset({"1", "2"})


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

    def load_operator_defaults(self) -> OperatorDefaults:
        values = self._load()
        fallback = OperatorDefaults()
        return OperatorDefaults(
            last_pass_num=str(values.get("last_pass_num", fallback.last_pass_num)),
            territory=str(values.get("territory", fallback.territory)),
            otb_post=str(values.get("otb_post", fallback.otb_post)),
            otb_name=str(values.get("otb_name", fallback.otb_name)),
            valid_until=str(values.get("valid_until", fallback.valid_until)),
            is_temporary_car=bool(
                values.get("is_temporary_car", fallback.is_temporary_car)
            ),
            print_mode=self._choice(
                values.get("print_mode"), _PRINT_MODES, fallback.print_mode
            ),
            badge_park=str(values.get("badge_park", fallback.badge_park)),
            badge_tab_num=str(values.get("badge_tab_num", fallback.badge_tab_num)),
            badge_print_mode=self._choice(
                values.get("badge_print_mode"),
                _BADGE_PRINT_MODES,
                fallback.badge_print_mode,
            ),
            auto_preview_target=self._choice(
                values.get("auto_preview_target"),
                _PREVIEW_TARGETS,
                fallback.auto_preview_target,
            ),
            warn_duplicates=bool(
                values.get("warn_duplicates", fallback.warn_duplicates)
            ),
            print_pass_back=bool(
                values.get("print_pass_back", fallback.print_pass_back)
            ),
        )

    def save_operator_defaults(self, defaults: OperatorDefaults) -> bool:
        self._validate_operator_defaults(defaults)
        return self._save(asdict(defaults))

    @staticmethod
    def _choice(value, supported: frozenset[str], fallback: str) -> str:
        candidate = str(value) if value is not None else fallback
        return candidate if candidate in supported else fallback

    @staticmethod
    def _validate_operator_defaults(defaults: OperatorDefaults) -> None:
        checks = (
            ("print_mode", defaults.print_mode, _PRINT_MODES),
            ("badge_print_mode", defaults.badge_print_mode, _BADGE_PRINT_MODES),
            ("auto_preview_target", defaults.auto_preview_target, _PREVIEW_TARGETS),
        )
        for field, value, supported in checks:
            if value not in supported:
                raise ValueError(f"Unsupported {field}: {value}")
