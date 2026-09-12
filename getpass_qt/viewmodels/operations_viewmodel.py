from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class OperationsViewModel(QObject):
    operations_changed = Signal(object)
    busy_changed = Signal(bool)
    operation_succeeded = Signal(str)
    operation_failed = Signal(str)

    def __init__(self, service, parent=None) -> None:
        super().__init__(parent)
        self._service = service
        self._operations = tuple(service.pending())

    @property
    def operations(self):
        return self._operations

    def refresh(self) -> bool:
        self.busy_changed.emit(True)
        try:
            operations = tuple(self._service.pending())
        except Exception as exc:
            self.operation_failed.emit(str(exc))
            return False
        finally:
            self.busy_changed.emit(False)
        self._operations = operations
        self.operations_changed.emit(operations)
        return True

    def confirm(self, ids) -> bool:
        return self._resolve(ids, self._service.confirm, "Операция подтверждена.")

    def cancel(self, ids) -> bool:
        return self._resolve(ids, self._service.cancel, "Операция отменена.")

    def find(self, operation_id: str):
        return next(
            (item for item in self._operations if item.id == operation_id),
            None,
        )

    def _resolve(self, ids, action, success_message: str) -> bool:
        operation_ids = tuple(ids)
        if not operation_ids:
            return False
        self.busy_changed.emit(True)
        try:
            action(operation_ids)
            operations = tuple(self._service.pending())
        except Exception as exc:
            self.operation_failed.emit(str(exc))
            return False
        finally:
            self.busy_changed.emit(False)
        self._operations = operations
        self.operations_changed.emit(operations)
        self.operation_succeeded.emit(success_message)
        return True
