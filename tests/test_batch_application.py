import csv

import pytest

from getpass_app.models.batch import BatchReviewRow
from getpass_app.services.batch_service import BatchService


class FakeJournal:
    def __init__(self, keys):
        self.schema = type("Schema", (), {"keys": keys})()


@pytest.fixture
def service():
    def validate(items, journal, badge=False):
        rows = []
        for index, item in enumerate(items, 2):
            errors = ["bad"] if item.get("force_error") else []
            warnings = ["warn"] if item.get("force_warning") else []
            rows.append((index, errors, warnings))
        return rows

    return BatchService(
        pass_journal=FakeJournal(["plate"]),
        badge_journal=FakeJournal(["tab_num"]),
        validate=validate,
    )


def test_read_csv_supports_utf8_sig_and_skips_header(tmp_path, service):
    path = tmp_path / "passes.csv"
    path.write_text("Номер;Госномер\n001-26;О777ТВ198\n", encoding="utf-8-sig")

    rows = service.read_csv(str(path))

    assert rows == (("001-26", "О777ТВ198"),)


def test_read_csv_falls_back_to_cp1251(tmp_path, service):
    path = tmp_path / "passes.csv"
    path.write_bytes("Номер;Госномер\n001-26;О777ТВ198\n".encode("cp1251"))

    rows = service.read_csv(str(path))

    assert rows == (("001-26", "О777ТВ198"),)


def test_parse_pass_rows_preserves_legacy_mapping(service):
    common = {
        "issue_date": "12.09.2026",
        "valid_until": "12.09.2027",
        "otb_post": "Инженер",
        "otb_name": "Петров П.П.",
        "is_temporary": False,
    }
    rows = ((
        "001-26",
        "О 777 ТВ 198",
        "ГАЗ",
        "Газель NEXT",
        "Служебный",
        "Белый",
        "Водитель 1-го класса",
        "Смирнов А.В.",
        "+7 921 111-22-33",
        'ПТО "Шаврова"',
    ),)

    items = service.parse_pass_rows(rows, common)

    assert items == ({
        "num": "001-26",
        "plate": "О 777 ТВ 198",
        "brand": "ГАЗ",
        "model": "Газель NEXT",
        "type": "Служебный",
        "color": "Белый",
        "d_pos": "Водитель 1-го класса",
        "d_fio": "Смирнов А.В.",
        "phone": "+7 921 111-22-33",
        "driver_full": "Водитель 1-го класса Смирнов А.В.",
        "territory": 'ПТО "Шаврова"',
        **common,
    },)


def test_parse_badge_rows_uses_csv_directory_for_relative_photo(tmp_path, service):
    photo = tmp_path / "ivanov.jpg"
    photo.write_bytes(b"photo")
    rows = ((
        "01035",
        "ИВАНОВ",
        "ИВАН",
        "ИВАНОВИЧ",
        "Водитель трамвая",
        "",
        "+7 921 123-45-67",
        "ivanov.jpg",
        "",
        "",
    ),)
    defaults = {
        "park": "ОСП ТП №8",
        "issue_date": "12.09.2026",
        "valid_until": "12.09.2027",
    }

    items = service.parse_badge_rows(rows, str(tmp_path), defaults)

    assert items[0]["tab_num"] == "01035"
    assert items[0]["fio"] == "ИВАНОВ ИВАН ИВАНОВИЧ"
    assert items[0]["park"] == "ОСП ТП №8"
    assert items[0]["photo_path"] == str(photo)
    assert items[0]["issue_date"] == "12.09.2026"
    assert items[0]["valid_until"] == "12.09.2027"


def test_parse_badge_rows_rejects_photo_path_escape(tmp_path, service):
    outside = tmp_path.parent / "outside.jpg"
    outside.write_bytes(b"photo")
    rows = (("01035", "ИВАНОВ", "ИВАН", "", "Водитель", "ТП", "", "../outside.jpg"),)

    with pytest.raises(ValueError, match="пределами"):
        service.parse_badge_rows(rows, str(tmp_path), {
            "park": "ТП",
            "issue_date": "12.09.2026",
            "valid_until": "12.09.2027",
        })


def test_review_projects_errors_warnings_and_summary(service):
    items = (
        {"plate": "A", "driver_full": "Driver A", "force_warning": True},
        {"plate": "B", "driver_full": "Driver B", "force_error": True},
        {"plate": "C", "driver_full": "Driver C"},
    )

    review = service.review("pass", items)

    assert review.total == 3
    assert review.error_count == 1
    assert review.warning_count == 1
    assert review.can_generate is False
    assert review.rows[0] == BatchReviewRow(
        row_number=2,
        number="A",
        person="Driver A",
        errors=(),
        warnings=("warn",),
    )
    assert review.rows[1].errors == ("bad",)


def test_export_template_writes_semicolon_utf8_sig_csv(tmp_path, service):
    path = tmp_path / "template.csv"

    service.export_template("pass", str(path))

    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.reader(stream, delimiter=";"))
    template = service.template("pass")
    assert rows == [list(template.header), list(template.sample)]
    assert template.filename == "Шаблон_массовой_печати_ТС.csv"


def test_badge_template_keeps_legacy_columns(service):
    template = service.template("badge")

    assert template.header == (
        "Табельный номер",
        "Фамилия",
        "Имя",
        "Отчество",
        "Должность",
        "Подразделение",
        "Телефон",
        "Имя_файла_фото",
        "Дата выдачи",
        "Действителен до",
    )
    assert template.filename == "Шаблон_массовой_печати_бейджей.csv"
