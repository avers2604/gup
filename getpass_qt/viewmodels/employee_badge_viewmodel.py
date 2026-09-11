from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from PySide6.QtCore import QObject, Signal

from getpass_app.models.employee_badge import (
    DEFAULT_BADGE_PARK,
    EmployeeBadgeData,
    EmployeeBadgeState,
    validate_employee_badge,
)
from getpass_app.services.employee_badge_service import (
    EmployeeBadgeOutputError,
    EmployeeBadgeService,
)
from getpass_core.domain import add_years_safe, format_date, parse_date

_BADGE_FIELDS = frozenset(EmployeeBadgeData.__dataclass_fields__)
_UPPER_FIELDS = frozenset({"surname", "name", "patronymic"})
_PRINT_MODES = frozenset({"card", "a4_grid", "a4_single"})


class EmployeeBadgeViewModel(QObject):
    state_changed = Signal(object)
    preview_changed = Signal(object)
    validation_changed = Signal(object)
    busy_changed = Signal(bool)
    operation_succeeded = Signal(str)
    operation_failed = Signal(str)

    def __init__(
        self,
        service: EmployeeBadgeService,
        *,
        now=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._now = now or datetime.now
        self._state = self._fresh_state()

    @property
    def state(self) -> EmployeeBadgeState:
        return self._state

    def roles(self) -> tuple[str, ...]:
        return self._service.roles()

    def printers(self) -> tuple[str, ...]:
        return self._service.printers()

    def warnings(self):
        return self._service.warnings(self._state)

    def set_field(self, field: str, value) -> None:
        if field not in _BADGE_FIELDS:
            raise ValueError(f"Unknown employee badge field: {field}")
        if field in _UPPER_FIELDS and isinstance(value, str):
            value = value.upper()
        data = replace(self._state.data, **{field: value})
        self._state = replace(self._state, data=data)
        self.state_changed.emit(self._state)

    def set_print_mode(self, mode: str) -> None:
        if mode not in _PRINT_MODES:
            raise ValueError(f"Unknown employee badge print mode: {mode}")
        self._state = replace(self._state, print_mode=mode)
        self.state_changed.emit(self._state)

    def set_years(self, years: int) -> bool:
        issue_date = parse_date(self._state.data.issue_date)
        if issue_date is None:
            self.operation_failed.emit("Сначала укажите корректную дату выдачи.")
            return False
        valid_until = format_date(add_years_safe(issue_date, int(years)))
        self.set_field("valid_until", valid_until)
        return True

    def store_photo(self, image) -> str:
        path = self._service.store_photo(image, self._state.data.tab_num)
        self.set_field("photo_path", path)
        return path

    def refresh_preview(self):
        image = self._service.render_preview(self._state.data)
        self.preview_changed.emit(image)
        return image

    def validate(self):
        issues = validate_employee_badge(self._state)
        self.validation_changed.emit(issues)
        return issues

    def save_pdf(self, path: str) -> bool:
        issues = self.validate()
        if issues:
            self.operation_failed.emit(issues[0].message)
            return False
        return self._run_output(
            lambda: self._service.save_pdf(self._state, path),
            "Пропуск работника сохранён.",
        )

    def print_badge(self, printer: str) -> bool:
        issues = self.validate()
        if issues:
            self.operation_failed.emit(issues[0].message)
            return False
        return self._run_output(
            lambda: self._service.print_badge(self._state, printer),
            "Пропуск работника отправлен на печать.",
        )

    def _run_output(self, action, success_message: str) -> bool:
        self.busy_changed.emit(True)
        try:
            result = action()
        except EmployeeBadgeOutputError as exc:
            self.operation_failed.emit(str(exc))
            return False
        finally:
            self.busy_changed.emit(False)

        self._reset_after_issue(result.next_tab_num)
        message = f"{success_message} Следующий табельный: {result.next_tab_num}"
        if result.overflowed:
            message += " Нумерация вышла за исходную разрядность."
        self.operation_succeeded.emit(message)
        return True

    def _reset_after_issue(self, next_tab_num: str) -> None:
        park = self._state.data.park or DEFAULT_BADGE_PARK
        print_mode = self._state.print_mode
        fresh = self._fresh_state(tab_num=next_tab_num, park=park)
        self._state = replace(fresh, print_mode=print_mode)
        self.state_changed.emit(self._state)

    def _fresh_state(
        self,
        *,
        tab_num: str = "",
        park: str = DEFAULT_BADGE_PARK,
    ) -> EmployeeBadgeState:
        now = self._now()
        data = EmployeeBadgeData(
            tab_num=tab_num,
            park=park,
            issue_date=format_date(now),
            valid_until=format_date(add_years_safe(now, 5)),
        )
        return EmployeeBadgeState(data=data)
