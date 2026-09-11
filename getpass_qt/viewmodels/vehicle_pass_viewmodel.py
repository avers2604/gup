from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QObject, Signal

from getpass_app.models.vehicle_pass import (
    VehiclePassData,
    VehiclePassState,
    validate_vehicle_state,
)
from getpass_app.services.vehicle_pass_service import (
    VehiclePassOutputError,
    VehiclePassService,
)
from getpass_core.domain import increment_number

_PASS_FIELDS = frozenset(VehiclePassData.__dataclass_fields__)
_VEHICLE_LOOKUP_FIELDS = {
    "brand": "brand",
    "model": "model",
    "type": "vehicle_type",
    "color": "color",
}


class VehiclePassViewModel(QObject):
    state_changed = Signal(object)
    preview_changed = Signal(object)
    validation_changed = Signal(object)
    busy_changed = Signal(bool)
    operation_succeeded = Signal(str)
    operation_failed = Signal(str)

    def __init__(self, service: VehiclePassService, parent=None) -> None:
        super().__init__(parent)
        self._service = service
        self._state = VehiclePassState()

    @property
    def state(self) -> VehiclePassState:
        return self._state

    def zones(self) -> tuple[str, ...]:
        return self._service.zones()

    def brands(self) -> tuple[str, ...]:
        return self._service.brands()

    def printers(self) -> tuple[str, ...]:
        return self._service.printers()

    def set_pass_field(self, slot: str, field: str, value) -> None:
        if slot not in ("first", "second"):
            raise ValueError(f"Unknown pass slot: {slot}")
        if field not in _PASS_FIELDS:
            raise ValueError(f"Unknown pass field: {field}")
        if field == "plate" and isinstance(value, str):
            value = value.upper()

        current = getattr(self._state, slot)
        updated = replace(current, **{field: value})
        self._state = replace(self._state, **{slot: updated})
        self.state_changed.emit(self._state)

    def set_common_field(self, field: str, value) -> None:
        if field not in self._state.common.__dataclass_fields__:
            raise ValueError(f"Unknown common field: {field}")
        common = replace(self._state.common, **{field: value})
        self._state = replace(self._state, common=common)
        self.state_changed.emit(self._state)

    def set_page_format(self, page_format: str) -> None:
        if page_format not in ("a4", "a5"):
            raise ValueError(f"Unknown page format: {page_format}")
        self._state = replace(self._state, page_format=page_format)
        self.state_changed.emit(self._state)

    def set_print_back(self, enabled: bool) -> None:
        self._state = replace(self._state, print_back=bool(enabled))
        self.state_changed.emit(self._state)

    def sync_second_number(self) -> None:
        self.set_pass_field(
            "second",
            "num",
            increment_number(self._state.first.num),
        )

    def autocomplete_vehicle(self, slot: str) -> bool:
        if slot not in ("first", "second"):
            raise ValueError(f"Unknown pass slot: {slot}")
        current = getattr(self._state, slot)
        if not current.plate.strip():
            return False
        cached = self._service.lookup_vehicle(current.plate)
        if not cached:
            return False

        values = {}
        for source, target in _VEHICLE_LOOKUP_FIELDS.items():
            existing = getattr(current, target)
            candidate = cached.get(source, "")
            if not str(existing).strip() and str(candidate).strip():
                values[target] = candidate
        if not values:
            return False

        updated = replace(current, **values)
        self._state = replace(self._state, **{slot: updated})
        self.state_changed.emit(self._state)
        return True

    def refresh_preview(self, slot: str = "first"):
        if slot not in ("first", "second"):
            raise ValueError(f"Unknown pass slot: {slot}")
        image = self._service.render_preview(
            getattr(self._state, slot),
            self._state.common,
        )
        self.preview_changed.emit(image)
        return image

    def validate(self):
        issues = validate_vehicle_state(self._state)
        self.validation_changed.emit(issues)
        return issues

    def save_pdf(self, path: str) -> bool:
        issues = self.validate()
        if issues:
            self.operation_failed.emit(issues[0].message)
            return False
        return self._run_output(
            lambda: self._service.save_pdf(self._state, path),
            "PDF сохранён.",
        )

    def print_passes(self, printer: str, *, confirm_flip=None) -> bool:
        issues = self.validate()
        if issues:
            self.operation_failed.emit(issues[0].message)
            return False
        return self._run_output(
            lambda: self._service.print_passes(
                self._state,
                printer,
                confirm_flip=confirm_flip,
            ),
            "Печать завершена.",
        )

    def _run_output(self, action, success_message: str) -> bool:
        self.busy_changed.emit(True)
        try:
            action()
        except VehiclePassOutputError as exc:
            self.operation_failed.emit(str(exc))
            return False
        finally:
            self.busy_changed.emit(False)
        self.operation_succeeded.emit(success_message)
        return True
