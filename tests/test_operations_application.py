from getpass_core import issuance, storage

from getpass_app.services.operations_service import OperationsService


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


def _pass_record(record_id):
    return {
        "id": record_id,
        "num": record_id,
        "plate": "А111АА78",
        "driver": "Иванов Иван",
        "issue_date": "12.09.2026",
        "valid_until": "12.09.2027",
    }


def _badge_record(record_id):
    return {
        "id": record_id,
        "tab_num": record_id,
        "fio": "ИВАНОВ И.И.",
        "role": "ВОДИТЕЛЬ",
        "issue_date": "12.09.2026",
        "valid_until": "12.09.2031",
    }


def test_pending_combines_journals_and_classifies_destinations(data_dir, tmp_path):
    pass_journal = _journal(data_dir, storage.PASS_SCHEMA, "ops_pass")
    badge_journal = _journal(data_dir, storage.BADGE_SCHEMA, "ops_badge")
    ready = tmp_path / "ready.pdf"
    ready.write_bytes(b"pdf")
    missing = tmp_path / "missing.png"

    direct_id = issuance.prepare(pass_journal, [_pass_record("p1")], "HP LaserJet")
    ready_id = issuance.prepare(badge_journal, [_badge_record("b1")], str(ready))
    missing_id = issuance.prepare(pass_journal, [_pass_record("p2")], str(missing))

    service = OperationsService(pass_journal=pass_journal, badge_journal=badge_journal)
    pending = service.pending()
    by_id = {item.id: item for item in pending}

    assert {item.id for item in pending} == {direct_id, ready_id, missing_id}
    assert by_id[direct_id].journal_key == "pass"
    assert by_id[direct_id].document_status == "Прямая печать"
    assert by_id[direct_id].document_path == ""
    assert by_id[ready_id].journal_key == "badge"
    assert by_id[ready_id].document_status == "Файл готов"
    assert by_id[ready_id].document_path == str(ready)
    assert by_id[missing_id].document_status == "Файл не найден"
    assert by_id[missing_id].document_path == str(missing)


def test_confirm_and_cancel_resolve_operation_to_owning_journal(data_dir):
    pass_journal = _journal(data_dir, storage.PASS_SCHEMA, "ops_pass_actions")
    badge_journal = _journal(data_dir, storage.BADGE_SCHEMA, "ops_badge_actions")
    pass_id = issuance.prepare(pass_journal, [_pass_record("p1")], "Printer")
    badge_id = issuance.prepare(badge_journal, [_badge_record("b1")], "Printer")
    service = OperationsService(pass_journal=pass_journal, badge_journal=badge_journal)

    service.confirm([pass_id])
    service.cancel([badge_id])

    assert [row["id"] for row in pass_journal.read()] == ["p1"]
    assert badge_journal.read() == []
    assert service.pending() == ()


def test_multi_action_keeps_existing_core_error_semantics(data_dir):
    pass_journal = _journal(data_dir, storage.PASS_SCHEMA, "ops_pass_missing")
    badge_journal = _journal(data_dir, storage.BADGE_SCHEMA, "ops_badge_missing")
    service = OperationsService(pass_journal=pass_journal, badge_journal=badge_journal)

    try:
        service.confirm(["missing"])
    except ValueError as exc:
        assert "Операция не найдена" in str(exc)
    else:
        raise AssertionError("missing operation must fail")
