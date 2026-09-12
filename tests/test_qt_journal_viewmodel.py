from getpass_app.models.journal import (
    JournalField,
    JournalHistoryEvent,
    JournalRow,
    JournalSnapshot,
)
from getpass_qt.viewmodels.journal_viewmodel import JournalViewModel


class FakeJournalService:
    def __init__(self):
        self.snapshot_calls = []
        self.updated = []
        self.revoked = []
        self.exported = []
        self.fail_snapshot = False

    def journal_keys(self):
        return ("pass", "badge")

    def snapshot(
        self,
        journal_key,
        filters,
        *,
        sort_key=None,
        sort_reverse=False,
        page=0,
        page_size=100,
    ):
        if self.fail_snapshot:
            raise RuntimeError("db unavailable")
        self.snapshot_calls.append(
            (journal_key, filters, sort_key, sort_reverse, page, page_size)
        )
        safe_page = min(max(page, 0), 2)
        return JournalSnapshot(
            journal_key=journal_key,
            journal_name="Тест",
            fields=(
                JournalField("id", "ID", 0),
                JournalField("plate", "Номер машины", 110),
                JournalField("status", "Статус", 115),
            ),
            rows=(
                JournalRow(
                    id="p1",
                    values={"id": "p1", "plate": "А111АА78", "status": "действует"},
                    state="active",
                ),
            ),
            total_records=5,
            filtered_records=5,
            page=safe_page,
            page_size=page_size,
            page_count=3,
        )

    def distinct(self, journal_key, key):
        return (f"{journal_key}:{key}",)

    def update_record(self, journal_key, record_id, values, expected):
        self.updated.append((journal_key, record_id, values, expected))

    def revoke(self, journal_key, ids, reason):
        self.revoked.append((journal_key, tuple(ids), reason))

    def history(self, journal_key, record_id):
        return (JournalHistoryEvent("now", "tester", "updated", ()),)

    def export(self, journal_key, rows, path):
        self.exported.append((journal_key, tuple(rows), path))
        return len(tuple(rows))

    def add_revoked_to_blacklist(self, journal_key, ids, reason):
        return len(tuple(ids))


def test_viewmodel_defaults_to_vehicle_journal_and_active_filter(qtbot):
    service = FakeJournalService()
    vm = JournalViewModel(service)

    assert vm.journal_key == "pass"
    assert vm.filters.status == "active"
    assert vm.snapshot.page == 0
    assert service.snapshot_calls[-1][0] == "pass"


def test_filter_change_resets_page_to_zero(qtbot):
    service = FakeJournalService()
    vm = JournalViewModel(service)
    vm.set_page(2)
    assert vm.snapshot.page == 2

    vm.set_search("Иванов")

    assert vm.snapshot.page == 0
    assert vm.filters.search == "Иванов"
    assert service.snapshot_calls[-1][4] == 0


def test_sorting_toggles_direction_for_same_column(qtbot):
    service = FakeJournalService()
    vm = JournalViewModel(service)

    vm.sort_by("plate")
    assert vm.sort_key == "plate"
    assert vm.sort_reverse is False

    vm.sort_by("plate")
    assert vm.sort_reverse is True
    assert service.snapshot_calls[-1][3] is True


def test_update_uses_snapshot_record_as_optimistic_expected_value(qtbot):
    service = FakeJournalService()
    vm = JournalViewModel(service)

    assert vm.update_record("p1", {"plate": "Б222ББ78"}) is True

    journal_key, record_id, values, expected = service.updated[0]
    assert journal_key == "pass"
    assert record_id == "p1"
    assert values == {"plate": "Б222ББ78"}
    assert expected["plate"] == "А111АА78"


def test_refresh_error_is_reported_without_replacing_last_snapshot(qtbot):
    service = FakeJournalService()
    vm = JournalViewModel(service)
    previous = vm.snapshot
    service.fail_snapshot = True
    messages = []
    vm.operation_failed.connect(messages.append)

    assert vm.refresh() is False

    assert vm.snapshot is previous
    assert messages == ["db unavailable"]
