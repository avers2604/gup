from dataclasses import dataclass
from typing import Literal

ThemeName = Literal["light", "dark"]
PrintMode = Literal["a4", "a5"]
BadgePrintMode = Literal["card", "a4_grid", "a4_single"]
PreviewTarget = Literal["1", "2"]


@dataclass(frozen=True)
class UiPreferences:
    theme: ThemeName = "light"


@dataclass(frozen=True)
class OperatorDefaults:
    last_pass_num: str = "001-26"
    territory: str = 'ПТО "Шаврова"'
    otb_post: str = ""
    otb_name: str = ""
    valid_until: str = "31.12.2026"
    is_temporary_car: bool = False
    print_mode: PrintMode = "a4"
    badge_park: str = "ОСП «Трамвайный парк № 8»"
    badge_tab_num: str = "01035"
    badge_print_mode: BadgePrintMode = "card"
    auto_preview_target: PreviewTarget = "1"
    warn_duplicates: bool = True
    print_pass_back: bool = False
