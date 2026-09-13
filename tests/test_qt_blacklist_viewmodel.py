from PySide6.QtTest import QSignalSpy

from getpass_app.models.blacklist import BlacklistEntry
from getpass_qt.viewmodels.blacklist_viewmodel import BlacklistViewModel


def make_entry(entry_id="abc123"):
    return BlacklistEntry(
        id=entry_id,
        plate="А111АА78",
        fio="ИВАНОВ И.И.",
        incident="Нарушение режима",
        created_at="13.09.2026 12:30",
    )


class FakeBlacklistService:
    def __init__(self):
        self.entries = [make_entry()]
        self.added = []
        self.removed = []
        self.error = None

    def list_entries(self):
        if self.error:
            raise self.error
        return tuple(self.entries)

    def add_entry(self, *, plate, fio, incident):
        if self.error:
            raise self.error
        self.added.append((plate, fio, incident))
        created = BlacklistEntry(
            id="new456",
            plate=plate.upper().replace(" ", ""),
            fio=" ".join(fio.upper().split()),
            incident=incident.strip(),
            created_at="13.09.2026 13:00",
        )
        self.entries.append(created)
        return created

    def remove_entry(self, entry_id):
        if self.error:
            raise self.error
        self.removed.append(entry_id)
        self.entries = [item for item in self.entries if item.id != entry_id]


def test_blacklist_viewmodel_refreshes_entries_and_emits_change(qtbot):
    service = FakeBlacklistService()
    vm = BlacklistViewModel(service)
    spy = QSignalSpy(vm.entries_changed)

    assert vm.entries == ()
    assert vm.refresh() is True

    assert vm.entries == tuple(service.entries)
    assert spy.count() == 1


def test_blacklist_viewmodel_adds_then_refreshes(qtbot):
    service = FakeBlacklistService()
    vm = BlacklistViewModel(service)
    success = QSignalSpy(vm.operation_succeeded)

    assert vm.add("а 222 аа 78", "петров п.п.", "Новый инцидент") is True

    assert service.added == [("а 222 аа 78", "петров п.п.", "Новый инцидент")]
    assert vm.entries[-1].id == "new456"
    assert success.count() == 1


def test_blacklist_viewmodel_removes_then_refreshes(qtbot):
    service = FakeBlacklistService()
    vm = BlacklistViewModel(service)
    vm.refresh()
    success = QSignalSpy(vm.operation_succeeded)

    assert vm.remove("abc123") is True

    assert service.removed == ["abc123"]
    assert vm.entries == ()
    assert success.count() == 1


def test_blacklist_viewmodel_reports_service_errors(qtbot):
    service = FakeBlacklistService()
    service.error = ValueError("Некорректные данные.")
    vm = BlacklistViewModel(service)
    failed = QSignalSpy(vm.operation_failed)

    assert vm.add("", "", "") is False

    assert failed.count() == 1
    assert failed.at(0)[0] == "Некорректные данные."
