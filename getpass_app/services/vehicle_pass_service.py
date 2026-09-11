from __future__ import annotations

from getpass_app.models.vehicle_pass import (
    VehiclePassCommon,
    VehiclePassData,
    VehiclePassState,
    validate_vehicle_state,
)
from getpass_core import issuance, printing
from getpass_core import render as R
from getpass_core.storage import (
    PASS_JOURNAL,
    known_car_brands,
    lookup_car,
    update_cars_cache,
)

DEFAULT_TERRITORIES = (
    'ПТО "Шаврова"',
    "Парковка",
    'ПТО "Шаврова", Парковка',
)


class VehiclePassOutputError(RuntimeError):
    pass


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
        journal=PASS_JOURNAL,
        prepare=issuance.prepare,
        confirm=issuance.confirm,
        cancel=issuance.cancel,
        save_document=printing.save_document,
        save_pdf_pages=printing.save_pdf_pages,
        print_one=printing.send_image_to_printer,
        print_two=printing.print_pass_two_sided,
        update_cache=update_cars_cache,
    ) -> None:
        self._lookup = lookup
        self._zone_values = zone_values or (lambda: PASS_JOURNAL.distinct("zone"))
        self._brand_values = brand_values
        self._render = render
        self._render_back = render_back
        self._build_a4 = build_a4
        self._journal = journal
        self._prepare = prepare
        self._confirm = confirm
        self._cancel = cancel
        self._save_document = save_document
        self._save_pdf_pages = save_pdf_pages
        self._print_one = print_one
        self._print_two = print_two
        self._update_cache = update_cache

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

    def save_pdf(self, state: VehiclePassState, path: str) -> None:
        records = self._validated_records(state)
        operation_id = self._prepare(self._journal, records, path)
        confirmed = False
        try:
            front, back = self.build_documents(state)
            if back is None:
                self._save_document(front, path)
            else:
                self._save_pdf_pages([front, back], path)
            self._confirm(self._journal, operation_id)
            confirmed = True
            self._update_cache(records)
        except BaseException as exc:
            if not confirmed:
                self._try_cancel(operation_id)
            raise VehiclePassOutputError(str(exc)) from exc

    def print_passes(
        self,
        state: VehiclePassState,
        printer: str,
        *,
        confirm_flip=None,
    ) -> None:
        records = self._validated_records(state)
        operation_id = self._prepare(self._journal, records, printer)
        confirmed = False
        try:
            front, back = self.build_documents(state)
            if back is None:
                ok, error = self._print_one(front, printer)
            else:
                ok, error = self._print_two(
                    front,
                    back,
                    printer,
                    confirm_flip=confirm_flip,
                )
            if not ok:
                raise VehiclePassOutputError(error or "Не удалось напечатать пропуск.")
            self._confirm(self._journal, operation_id)
            confirmed = True
            self._update_cache(records)
        except BaseException as exc:
            if not confirmed:
                self._try_cancel(operation_id)
            if isinstance(exc, VehiclePassOutputError):
                raise
            raise VehiclePassOutputError(str(exc)) from exc

    def _validated_records(self, state: VehiclePassState) -> list[dict[str, object]]:
        issues = validate_vehicle_state(state)
        if issues:
            raise VehiclePassOutputError(issues[0].message)

        passes = [state.first]
        if state.page_format == "a4" and not state.second.is_empty:
            passes.append(state.second)

        records = []
        for pass_data in passes:
            record = pass_data.to_renderer_dict()
            record["issue_date"] = state.common.issue_date.strip()
            record["valid_until"] = state.common.valid_until.strip()
            records.append(record)
        return records

    def _try_cancel(self, operation_id: str) -> None:
        try:
            self._cancel(self._journal, operation_id)
        except Exception:
            pass
