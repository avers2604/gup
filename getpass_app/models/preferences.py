from dataclasses import dataclass
from typing import Literal

ThemeName = Literal["light", "dark"]


@dataclass(frozen=True)
class UiPreferences:
    theme: ThemeName = "light"
