from dataclasses import replace

import pytest
from PIL import Image

from getpass_app.models.employee_badge import EmployeeBadgeData, EmployeeBadgeState
from getpass_app.services.employee_badge_service import (
    EmployeeBadgeOutputError,
    EmployeeBadgeService,
)


class FakeJournal:
    def __init__(self):
        self.duplicates = []
        self.roles = ["Водитель", "Слесарь"]

    def find_duplicates(self, tab_num):
        return [item for item in self.duplicates if item.get("tab_num") == tab_num]

    def distinct(self, field):
        assert field == "role"
        return list(self.roles)


class ServiceHarness:
    def __init__(self, tmp_path):
        self.events = []
        self.journal = FakeJournal()
        self.blacklist_items = []
        self.tmp_path = tmp_path

    def render(self, _data):
        self.events.append("render")
        return Image.new("RGB", (850, 540), "white")

    @staticmethod
    def grid(_images):
        return Image.new("RGB", (2480, 3508), "white")

    @staticmethod
    def single(_image):
        return Image.new("RGB", (2480, 3508), "white")

    def blacklist(self, *, fio):
        assert fio
        return list(self.blacklist_items)

    def prepare(self, _journal, _records, _target):
        self.events.append("prepare")
        return "op-1"

    def confirm(self, _journal, operation_id):
        assert operation_id == "op-1"
        self.events.append("confirm")

    def cancel(self, _journal, operation_id):
        assert operation_id == "op-1"
        self.events.append("cancel")

    def save(self, _document, _path):
        self.events.append("save")

    def print_one(self, _document, _printer):
        self.events.append("print")
        return True, None

    def service(self):
        return EmployeeBadgeService(
            journal=self.journal,
            blacklist_lookup=self.blacklist,
            printer_values=lambda: ("Printer A",),
            render=self.render,
            build_grid=self.grid,
            build_single=self.single,
            prepare=self.prepare,
            confirm=self.confirm,
            cancel=self.cancel,
            save_document=self.save,
            print_one=self.print_one,
            photo_dir=str(self.tmp_path / "photos"),
            file_exists=lambda _path: True,
        )


def valid_state(**changes):
    values = {
        "tab_num": "01035",
        "park": 'ОСП «Трамвайный парк № 5»',
        "role": "ВОДИТЕЛЬ",
        "surname": "ИВАНОВ",
        "name": "ИВАН",
        "patronymic": "ИВАНОВИЧ",
        "phone": "+79990000000",
        "issue_date": "12.09.2026",
        "valid_until": "12.09.2031",
        "photo_path": "photo.jpg",
    }
    values.update(changes)
    return EmployeeBadgeState(data=EmployeeBadgeData(**values))


def test_roles_and_printers_are_delegated(tmp_path):
    harness = ServiceHarness(tmp_path)
    service = harness.service()

    assert service.roles() == ("Водитель", "Слесарь")
    assert service.printers() == ("Printer A",)


def test_warnings_collect_duplicates_and_blacklist(tmp_path):
    harness = ServiceHarness(tmp_path)
    harness.journal.duplicates = [{"tab_num": "01035", "fio": "ИВАНОВ ИВАН"}]
    harness.blacklist_items = [{"incident": "test"}]
    service = harness.service()

    warnings = service.warnings(valid_state())

    assert warnings.duplicates[0]["tab_num"] == "01035"
    assert warnings.blacklist[0]["incident"] == "test"


def test_build_document_preserves_three_legacy_modes(tmp_path):
    service = ServiceHarness(tmp_path).service()
    state = valid_state()

    card = service.build_document(state)
    grid = service.build_document(replace(state, print_mode="a4_grid"))
    single = service.build_document(replace(state, print_mode="a4_single"))

    assert card.mode == "card"
    assert card.image.size == (850, 540)
    assert grid.mode == "a4_grid"
    assert grid.image.size == (2480, 3508)
    assert single.mode == "a4_single"
    assert single.image.size == (2480, 3508)


def test_store_photo_writes_uuid_jpeg_to_configured_directory(tmp_path):
    service = ServiceHarness(tmp_path).service()
    image = Image.new("RGB", (300, 400), "white")

    path = service.store_photo(image, "01035")

    assert path.endswith(".jpg")
    assert (tmp_path / "photos") in __import__("pathlib").Path(path).parents
    assert __import__("pathlib").Path(path).exists()


def test_save_pdf_uses_prepare_output_confirm_order(tmp_path):
    harness = ServiceHarness(tmp_path)
    service = harness.service()

    result = service.save_pdf(valid_state(), str(tmp_path / "badge.pdf"))

    assert harness.events == ["prepare", "render", "save", "confirm"]
    assert result.next_tab_num == "01036"


def test_save_pdf_cancels_prepared_issuance_on_output_error(tmp_path):
    harness = ServiceHarness(tmp_path)

    def fail_save(_document, _path):
        harness.events.append("save")
        raise OSError("disk")

    service = EmployeeBadgeService(
        journal=harness.journal,
        blacklist_lookup=harness.blacklist,
        render=harness.render,
        build_grid=harness.grid,
        build_single=harness.single,
        prepare=harness.prepare,
        confirm=harness.confirm,
        cancel=harness.cancel,
        save_document=fail_save,
        print_one=harness.print_one,
        photo_dir=str(tmp_path / "photos"),
        file_exists=lambda _path: True,
    )

    with pytest.raises(EmployeeBadgeOutputError, match="disk"):
        service.save_pdf(valid_state(), str(tmp_path / "badge.pdf"))

    assert harness.events == ["prepare", "render", "save", "cancel"]


def test_print_badge_confirms_only_after_successful_print(tmp_path):
    harness = ServiceHarness(tmp_path)
    service = harness.service()

    result = service.print_badge(valid_state(), "Printer A")

    assert harness.events == ["prepare", "render", "print", "confirm"]
    assert result.next_tab_num == "01036"


def test_output_rejects_missing_photo_file(tmp_path):
    harness = ServiceHarness(tmp_path)
    service = EmployeeBadgeService(
        journal=harness.journal,
        blacklist_lookup=harness.blacklist,
        render=harness.render,
        build_grid=harness.grid,
        build_single=harness.single,
        prepare=harness.prepare,
        confirm=harness.confirm,
        cancel=harness.cancel,
        save_document=harness.save,
        print_one=harness.print_one,
        photo_dir=str(tmp_path / "photos"),
        file_exists=lambda _path: False,
    )

    with pytest.raises(EmployeeBadgeOutputError, match="фотограф"):
        service.save_pdf(valid_state(), str(tmp_path / "badge.pdf"))

    assert harness.events == []
