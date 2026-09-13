from datetime import date

import pytest

from getpass_core import storage

from getpass_app.models.journal import JournalFilters
from getpass_app.services.journal_service import JournalService


def _journal(data_dir, base_schema, table):
    schema = storage.JournalSchema(
        name=base_schema.name,
        csv_path=str(data_dir / f"{table}.csv"),
        xlsx_path=str(data_dir / f"{table}.xlsx"),
        fields=base_schema.fields,
        table=table,
        dup_key=base_schema.dup_key,
        legacy_layouts=base_schema.legacy_layouts,
    )
    return storage.Journal(schema)


@pytest.fixture
def journals(data_dir):
    return (
        _journal(data_dir, storage.PASS_SCHEMA, "phase4_pass_journal"),
        _journal(data_dir, storage.BADGE_SCHEMA, "phase4_badge_journal"),
    )


@pytest.fixture
def service(journals):
    pass_journal, badge_journal = journals
    return JournalService(
        pass_journal=pass_journal,
        badge_journal=badge_journal,
        today=lambda: date(2026, 9, 12),
    )


def _seed_passes(journal):
    journal.append_many(
        [
            {
                "id": "p1",
                "num": "001",
                "plate": "А111АА78",
                "zone": "Парковка",
                "driver": "Иванов Иван",
                "issue_date": "01.09.2026",
                "valid_until": "20.09.2026",
            },
            {
                "id": "p2",
                "num": "002",
                "plate": "Б222ББ78",
                "zone": "Депо",
                "driver": "Петров Пётр",
                "issue_date": "02.09.2026",
                "valid_until": "10.09.2026",
            },
            {
                "id": "p3",
                "num": "003",
                "plate": "В333ВВ78",
                "zone": "Парковка",
                "driver": "Сидоров Сидор",
                "issue_date": "03.09.2026",
                "valid_until": "",
            },
        ]
    )
    journal.revoke_ids(["p3"], "тест", when="11.09.2026")
    journal.append_many(
        [
            {
                "id": "p4",
                "num": "004",
                "plate": "Г444ГГ78",
                "zone": "Парковка",
                "driver": "Иванов Алексей",
                "issue_date": "04.09.2026",
                "valid_until": "",
            }
        ]
    )


def test_snapshot_preserves_tk_filter_semantics(service, journals):
    pass_journal, _ = journals
    _seed_passes(pass_journal)

    filters = JournalFilters(
        search="иванов",
        status="active",
        date_from="01.09.2026",
        date_to="30.09.2026",
        extra=(("zone", "Парковка"),),
    )
    snapshot = service.snapshot("pass", filters)

    assert snapshot.total_records == 4
    assert snapshot.filtered_records == 1
    assert [row.id for row in snapshot.rows] == ["p1"]
    assert snapshot.rows[0].state == "active"
    assert snapshot.rows[0].values["driver"] == "Иванов Иван"


def test_snapshot_computes_expired_unknown_and_revoked_states(service, journals):
    pass_journal, _ = journals
    _seed_passes(pass_journal)

    snapshot = service.snapshot("pass", JournalFilters(status="all"))
    states = {row.id: row.state for row in snapshot.rows}

    assert states == {
        "p1": "active",
        "p2": "expired",
        "p3": "revoked",
        "p4": "unknown",
    }


def test_snapshot_sorts_before_paginating_and_clamps_page(service, journals):
    pass_journal, _ = journals
    _seed_passes(pass_journal)

    snapshot = service.snapshot(
        "pass",
        JournalFilters(status="all"),
        sort_key="plate",
        sort_reverse=True,
        page=99,
        page_size=2,
    )

    assert snapshot.page == 1
    assert snapshot.page_count == 2
    assert [row.id for row in snapshot.rows] == ["p2", "p1"]


def test_update_record_keeps_optimistic_concurrency_guard(service, journals):
    pass_journal, _ = journals
    _seed_passes(pass_journal)
    expected = next(row for row in pass_journal.read() if row["id"] == "p1")

    service.update_record("pass", "p1", {"driver": "Новый водитель"}, expected)
    assert next(row for row in pass_journal.read() if row["id"] == "p1")["driver"] == "Новый водитель"

    with pytest.raises(ValueError, match="изменена в другом окне"):
        service.update_record("pass", "p1", {"driver": "Ещё один"}, expected)


def test_history_projects_immutable_event_changes(service, journals):
    pass_journal, _ = journals
    pass_journal.append_many(
        [{
            "id": "p1",
            "num": "001",
            "plate": "А111АА78",
            "driver": "Иванов Иван",
            "issue_date": "01.09.2026",
            "valid_until": "20.09.2026",
        }]
    )
    expected = pass_journal.read()[0]
    service.update_record("pass", "p1", {"driver": "Петров Пётр"}, expected)

    events = service.history("pass", "p1")

    assert events[-1].action == "updated"
    assert [(change.key, change.before, change.after) for change in events[-1].changes] == [
        ("driver", "Иванов Иван", "Петров Пётр")
    ]


def test_export_writes_exactly_the_rows_supplied(journals, tmp_path):
    pass_journal, badge_journal = journals
    _seed_passes(pass_journal)
    calls = []

    def fake_export(rows, cols_def, path, sheet_name):
        calls.append((rows, cols_def, path, sheet_name))

    service = JournalService(
        pass_journal=pass_journal,
        badge_journal=badge_journal,
        today=lambda: date(2026, 9, 12),
        export_xlsx=fake_export,
    )
    snapshot = service.snapshot(
        "pass",
        JournalFilters(search="А111", status="all"),
    )
    target = str(tmp_path / "filtered.xlsx")

    count = service.export("pass", snapshot.rows, target)

    assert count == 1
    assert calls[0][2] == target
    assert calls[0][3] == storage.PASS_SCHEMA.name
    plate_index = storage.PASS_SCHEMA.keys.index("plate")
    assert calls[0][0][0][plate_index] == "А111АА78"


def test_revoke_can_offer_same_one_shot_blacklist_behavior(journals):
    pass_journal, badge_journal = journals
    pass_journal.append_many(
        [{
            "id": "p1",
            "plate": "А111АА78",
            "driver": "Иванов Иван",
            "issue_date": "01.09.2026",
            "valid_until": "20.09.2026",
        }]
    )
    added = []
    service = JournalService(
        pass_journal=pass_journal,
        badge_journal=badge_journal,
        blacklist_add=lambda plate, fio, reason: added.append((plate, fio, reason)),
    )

    service.revoke("pass", ["p1"], "нарушение")
    service.add_revoked_to_blacklist("pass", ["p1"], "нарушение")

    assert pass_journal.read()[0]["status"] == storage.STATUS_REVOKED
    assert added == [("А111АА78", "Иванов Иван", "нарушение")]
