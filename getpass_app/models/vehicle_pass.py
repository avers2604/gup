from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from getpass_core.domain import normalize_plate


@dataclass(frozen=True)
class VehiclePassData:
    num: str = ""
    plate: str = ""
    brand: str = ""
    model: str = ""
    vehicle_type: str = ""
    color: str = ""
    driver_position: str = ""
    driver_name: str = ""
    phone: str = ""
    territory: str = ""

    @property
    def is_empty(self) -> bool:
        return not any(
            (
                self.plate.strip(),
                self.brand.strip(),
                self.model.strip(),
                self.vehicle_type.strip(),
                self.color.strip(),
            )
        )

    def to_renderer_dict(self, *, placeholder: bool = False) -> dict[str, object]:
        position = self.driver_position.strip()
        driver_name = self.driver_name.strip()
        driver_full = f"{position} {driver_name}".strip()
        if placeholder and not driver_full:
            driver_full = "Должность  Фамилия И.О."

        plate = normalize_plate(self.plate)
        if placeholder and not plate:
            plate = "А 000 АА 00"

        number = self.num.strip()
        if not number:
            number = "000-00" if placeholder else "б/н"

        return {
            "num": number,
            "plate": plate,
            "brand": self.brand.strip(),
            "model": self.model.strip(),
            "type": self.vehicle_type.strip(),
            "color": self.color.strip(),
            "d_pos": position,
            "d_fio": driver_name,
            "phone": self.phone.strip(),
            "driver_full": driver_full,
            "territory": self.territory.strip(),
        }


@dataclass(frozen=True)
class VehiclePassCommon:
    issue_date: str = ""
    valid_until: str = ""
    is_temporary: bool = False
    otb_post: str = ""
    otb_name: str = ""

    def to_renderer_dict(self) -> dict[str, object]:
        return {
            "issue_date": self.issue_date.strip(),
            "valid_until": self.valid_until.strip(),
            "is_temporary": self.is_temporary,
            "otb_post": self.otb_post.strip(),
            "otb_name": self.otb_name.strip(),
        }


@dataclass(frozen=True)
class VehiclePassState:
    first: VehiclePassData = field(default_factory=VehiclePassData)
    second: VehiclePassData = field(default_factory=VehiclePassData)
    common: VehiclePassCommon = field(default_factory=VehiclePassCommon)
    page_format: Literal["a4", "a5"] = "a4"
    print_back: bool = False


@dataclass(frozen=True)
class ValidationIssue:
    field: str
    message: str


def validate_vehicle_state(state: VehiclePassState) -> tuple[ValidationIssue, ...]:
    issues: list[ValidationIssue] = []
    if not state.first.plate.strip():
        issues.append(
            ValidationIssue(
                "first.plate",
                "Укажите государственный регистрационный знак.",
            )
        )
    if not state.second.is_empty and not state.second.plate.strip():
        issues.append(
            ValidationIssue(
                "second.plate",
                "Укажите государственный регистрационный знак.",
            )
        )
    return tuple(issues)
