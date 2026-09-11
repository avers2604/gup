from __future__ import annotations

from getpass_app.models.vehicle_pass import (
    VehiclePassCommon,
    VehiclePassData,
    VehiclePassState,
)
from getpass_core import render as R
from getpass_core.storage import PASS_JOURNAL, known_car_brands, lookup_car

DEFAULT_TERRITORIES = (
    'ПТО "Шаврова"',
    "Парковка",
    'ПТО "Шаврова", Парковка',
)


class VehiclePassService:
    def __init__(
        self,
        *,
        lookup=lookup_car,
        zone_values=None,
        brand_values=known_car_brands,
        render=R.render_pass,
        render_back=R.render_pass_back,
        build_a4=R.build_pass_a4_sheet,
    ) -> None:
        self._lookup = lookup
        self._zone_values = zone_values or (lambda: PASS_JOURNAL.distinct("zone"))
        self._brand_values = brand_values
        self._render = render
        self._render_back = render_back
        self._build_a4 = build_a4

    def lookup_vehicle(self, plate: str) -> dict[str, str] | None:
        car = self._lookup(plate)
        if not car:
            return None
        return {
            key: (car.get(key) or "")
            for key in ("brand", "model", "type", "color")
        }

    def zones(self) -> tuple[str, ...]:
        values = []
        for value in (*DEFAULT_TERRITORIES, *self._zone_values()):
            clean = (value or "").strip()
            if clean and clean not in values:
                values.append(clean)
        return tuple(values)

    def brands(self) -> tuple[str, ...]:
        return tuple(self._brand_values())

    def render_preview(
        self,
        data: VehiclePassData,
        common: VehiclePassCommon,
    ):
        return self._render(
            data.to_renderer_dict(placeholder=True),
            common.to_renderer_dict(),
        )

    def build_documents(self, state: VehiclePassState):
        common = state.common.to_renderer_dict()
        first = self._render(state.first.to_renderer_dict(), common)

        if state.page_format == "a5":
            back = self._render_back() if state.print_back else None
            return first, back

        second = None
        if not state.second.is_empty:
            second = self._render(state.second.to_renderer_dict(), common)
        front = self._build_a4(first, second)

        back = None
        if state.print_back:
            back_first = self._render_back()
            back_second = self._render_back() if second is not None else None
            back = self._build_a4(back_first, back_second)
        return front, back
