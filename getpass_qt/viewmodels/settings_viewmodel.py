from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QObject, Signal

from getpass_app.models.preferences import OperatorDefaults

_SETTINGS_FIELDS = frozenset(OperatorDefaults.__dataclass_fields__)


class SettingsViewModel(QObject):
    state_changed = Signal(object)
    operation_succeeded = Signal(str)
    operation_failed = Signal(str)

    def __init__(
        self,
        service,
        *,
        defaults: OperatorDefaults,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._defaults = defaults

    @property
    def defaults(self) -> OperatorDefaults:
        return self._defaults

    def set_field(self, field: str, value) -> None:
        if field not in _SETTINGS_FIELDS:
            raise ValueError(f"Unknown settings field: {field}")
        self._defaults = replace(self._defaults, **{field: value})
        self.state_changed.emit(self._defaults)

    def save(self) -> bool:
        try:
            saved = self._service.save_operator_defaults(self._defaults)
        except Exception as exc:
            self.operation_failed.emit(str(exc))
            return False
        if not saved:
            self.operation_failed.emit("Не удалось сохранить настройки.")
            return False
        self.operation_succeeded.emit("Настройки сохранены.")
        return True
