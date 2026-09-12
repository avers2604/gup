from __future__ import annotations

import csv
from pathlib import Path

from getpass_app.models.batch import (
    BatchKind,
    BatchReview,
    BatchReviewRow,
    BatchTemplate,
)
from getpass_core.importing import photo_in_folder, validate_items
from getpass_core.storage import BADGE_JOURNAL, PASS_JOURNAL

_PASS_TEMPLATE = BatchTemplate(
    kind="pass",
    header=(
        "Номер пропуска",
        "Госномер",
        "Марка",
        "Модель",
        "Вид",
        "Цвет",
        "Должность водителя",
        "ФИО водителя",
        "Телефон",
        "Зона допуска",
    ),
    sample=(
        "001-26",
        "О 777 ТВ 198",
        "ГАЗ",
        "Газель NEXT",
        "Служебный",
        "Белый",
        "Водитель 1-го класса",
        "Смирнов А.В.",
        "+7 (921) 111-22-33",
        'ПТО "Шаврова"',
    ),
    filename="Шаблон_массовой_печати_ТС.csv",
)

_BADGE_TEMPLATE = BatchTemplate(
    kind="badge",
    header=(
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
    ),
    sample=(
        "01035",
        "ИВАНОВ",
        "ИВАН",
        "ИВАНОВИЧ",
        "Водитель трамвая",
        "ОСП «Трамвайный парк № 8»",
        "+7 (921) 123-45-67",
        "ivanov.jpg",
        "",
        "",
    ),
    filename="Шаблон_массовой_печати_бейджей.csv",
)

_TEMPLATES = {"pass": _PASS_TEMPLATE, "badge": _BADGE_TEMPLATE}


class BatchService:
    def __init__(
        self,
        *,
        pass_journal=PASS_JOURNAL,
        badge_journal=BADGE_JOURNAL,
        validate=validate_items,
        photo_lookup=photo_in_folder,
    ) -> None:
        self._journals = {"pass": pass_journal, "badge": badge_journal}
        self._validate = validate
        self._photo_lookup = photo_lookup

    @staticmethod
    def template(kind: BatchKind) -> BatchTemplate:
        return _TEMPLATES[kind]

    @staticmethod
    def read_csv(path: str) -> tuple[tuple[str, ...], ...]:
        rows = None
        for encoding in ("utf-8-sig", "cp1251", "utf-8"):
            try:
                with open(path, "r", encoding=encoding, newline="") as stream:
                    rows = list(csv.reader(stream, delimiter=";"))
                break
            except UnicodeDecodeError:
                continue
        if rows is None:
            return ()
        return tuple(tuple(row) for row in rows[1:])

    @staticmethod
    def parse_pass_rows(rows, common) -> tuple[dict, ...]:
        items = []
        for row in rows:
            if len(row) < 2 or not row[1].strip():
                continue
            cell = BatchService._cell_reader(row)
            position = cell(6)
            fio = cell(7)
            items.append({
                "num": cell(0),
                "plate": cell(1),
                "brand": cell(2),
                "model": cell(3),
                "type": cell(4, "Служебный"),
                "color": cell(5),
                "d_pos": position,
                "d_fio": fio,
                "phone": cell(8),
                "driver_full": f"{position} {fio}".strip(),
                "territory": cell(9),
                **common,
            })
        return tuple(items)

    def parse_badge_rows(self, rows, folder: str, defaults) -> tuple[dict, ...]:
        items = []
        for row in rows:
            if len(row) < 4 or not row[1].strip():
                continue
            cell = self._cell_reader(row)
            photo_path = self._photo_lookup(folder, cell(7))
            surname, name, patronymic = cell(1), cell(2), cell(3)
            items.append({
                "tab_num": cell(0),
                "surname": surname,
                "name": name,
                "patronymic": patronymic,
                "fio": " ".join(
                    part for part in (surname, name, patronymic) if part
                ),
                "role": cell(4, "Сотрудник"),
                "park": cell(5) or defaults["park"],
                "phone": cell(6),
                "photo_path": photo_path,
                "issue_date": cell(8) or defaults["issue_date"],
                "valid_until": cell(9) or defaults["valid_until"],
            })
        return tuple(items)

    def review(self, kind: BatchKind, items) -> BatchReview:
        journal = self._journals[kind]
        results = self._validate(items, journal, badge=kind == "badge")
        rows = []
        for item, (row_number, errors, warnings) in zip(items, results):
            rows.append(BatchReviewRow(
                row_number=row_number,
                number=str(item.get("tab_num" if kind == "badge" else "plate", "")),
                person=str(item.get("fio" if kind == "badge" else "driver_full", "")),
                errors=tuple(errors),
                warnings=tuple(warnings),
            ))
        return BatchReview(kind=kind, rows=tuple(rows))

    def export_template(self, kind: BatchKind, path: str) -> None:
        template = self.template(kind)
        target = Path(path)
        with target.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream, delimiter=";")
            writer.writerow(template.header)
            writer.writerow(template.sample)

    @staticmethod
    def _cell_reader(row):
        def cell(index: int, default: str = "") -> str:
            return row[index].strip() if len(row) > index else default

        return cell
