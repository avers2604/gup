from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class BlacklistViewModel(QObject):
    entries_changed = Signal(object)
    operation_succeeded = Signal(str)
    operation_failed = Signal(str)

    def __init__(self, service, parent=None) -> None:
        super().__init__(parent)
        self._service = service
        self._entries = ()

    @property
    def entries(self):
        return self._entries

    def refresh(self) -> bool:
        try:
            entries = tuple(self._service.list_entries())
        except Exception as exc:
            self.operation_failed.emit(str(exc))
            return False
        self._entries = entries
        self.entries_changed.emit(entries)
        return True

    def add(self, plate: str, fio: str, incident: str) -> bool:
        try:
            self._service.add_entry(
                plate=plate,
                fio=fio,
                incident=incident,
            )
        except Exception as exc:
            self.operation_failed.emit(str(exc))
            return False
        if not self.refresh():
            return False
        self.operation_succeeded.emit("Запись добавлена в черный список.")
        return True

    def remove(self, entry_id: str) -> bool:
        try:
            self._service.remove_entry(entry_id)
        except Exception as exc:
            self.operation_failed.emit(str(exc))
            return False
        if not self.refresh():
            return False
        self.operation_succeeded.emit("Запись удалена из черного списка.")
        return True
