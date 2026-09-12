from __future__ import annotations

import csv
import threading
from pathlib import Path

from PIL import ImageDraw

from getpass_app.models.batch import (
    BatchKind,
    BatchOutputResult,
    BatchReview,
    BatchReviewRow,
    BatchTemplate,
)
from getpass_core import issuance
from getpass_core import render as R
from getpass_core.importing import photo_in_folder, validate_items
from getpass_core.printing import save_pdf_pages
from getpass_core.storage import (
    BADGE_JOURNAL,
    PASS_JOURNAL,
    update_cars_cache,
)

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


class BatchCancelled(Exception):
    pass


class BatchOutputError(RuntimeError):
    pass


def _decorate_pass_sheet(image) -> None:
    draw = ImageDraw.Draw(image)
    R.draw_sheet_brand_icons(draw, 140, 52, size=44)


class BatchService:
    def __init__(
        self,
        *,
        pass_journal=PASS_JOURNAL,
        badge_journal=BADGE_JOURNAL,
        validate=validate_items,
        photo_lookup=photo_in_folder,
        render_pass=R.render_pass,
        build_pass_sheet=R.build_pass_a4_sheet,
        decorate_pass_sheet=_decorate_pass_sheet,
        render_badge=R.render_single_badge_image,
        build_badge_grid=R.build_badge_a4_grid,
        save_pdf_pages=save_pdf_pages,
        prepare=issuance.prepare,
        confirm=issuance.confirm,
        cancel=issuance.cancel,
        update_cache=update_cars_cache,
    ) -> None:
        self._journals = {"pass": pass_journal, "badge": badge_journal}
        self._validate = validate
        self._photo_lookup = photo_lookup
        self._render_pass = render_pass
        self._build_pass_sheet = build_pass_sheet
        self._decorate_pass_sheet = decorate_pass_sheet
        self._render_badge = render_badge
        self._build_badge_grid = build_badge_grid
        self._save_pdf_pages = save_pdf_pages
        self._prepare = prepare
        self._confirm = confirm
        self._cancel = cancel
        self._update_cache = update_cache

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

    def generate_pdf(
        self,
        kind: BatchKind,
        items,
        path: str,
        *,
        cancelled=None,
        progress=None,
    ) -> BatchOutputResult:
        items = tuple(items)
        if not items:
            raise BatchOutputError("Нечего печатать.")
        cancelled = cancelled or threading.Event()
        if cancelled.is_set():
            raise BatchCancelled()

        journal = self._journals[kind]
        records = self._journal_records(kind, items)
        operation_id = self._prepare(journal, records, path)
        total = self._page_count(kind, len(items))
        pages = self._pages(kind, items, total, cancelled, progress)
        try:
            self._save_pdf_pages(pages, path)
        except BatchCancelled:
            self._try_cancel(journal, operation_id)
            raise
        except Exception as exc:
            self._try_cancel(journal, operation_id)
            raise BatchOutputError(str(exc)) from exc

        try:
            self._confirm(journal, operation_id)
        except Exception as exc:
            raise BatchOutputError(str(exc)) from exc

        if kind == "pass":
            try:
                self._update_cache(items)
            except Exception as exc:
                raise BatchOutputError(str(exc)) from exc
        return BatchOutputResult(
            kind=kind,
            path=path,
            item_count=len(items),
            page_count=total,
        )

    def _pages(self, kind, items, total, cancelled, progress):
        builder = self._pass_page if kind == "pass" else self._badge_page
        step = 2 if kind == "pass" else 9
        for page_index, start in enumerate(range(0, len(items), step), 1):
            if cancelled.is_set():
                raise BatchCancelled()
            yield builder(items, start)
            if progress is not None:
                progress(page_index, total)

    def _pass_page(self, items, start):
        common = self._pass_common(items[start])
        first = self._render_pass(items[start], common)
        second = None
        if start + 1 < len(items):
            second = self._render_pass(items[start + 1], common)
        sheet = self._build_pass_sheet(first, second)
        self._decorate_pass_sheet(sheet)
        return sheet

    def _badge_page(self, items, start):
        images = [self._render_badge(item) for item in items[start:start + 9]]
        return self._build_badge_grid(images)

    @staticmethod
    def _pass_common(item):
        return {
            "issue_date": item.get("issue_date", ""),
            "valid_until": item.get("valid_until", ""),
            "otb_post": item.get("otb_post", ""),
            "otb_name": item.get("otb_name", ""),
            "is_temporary": bool(item.get("is_temporary")),
        }

    @staticmethod
    def _journal_records(kind, items):
        if kind == "badge":
            return tuple(dict(item) for item in items)
        records = []
        for item in items:
            record = dict(item)
            record["zone"] = item.get("territory") or "Основная (Без зоны)"
            record["driver"] = item.get("driver_full", "")
            records.append(record)
        return tuple(records)

    @staticmethod
    def _page_count(kind, item_count: int) -> int:
        per_page = 2 if kind == "pass" else 9
        return (item_count + per_page - 1) // per_page

    def _try_cancel(self, journal, operation_id) -> None:
        try:
            self._cancel(journal, operation_id)
        except Exception:
            pass

    @staticmethod
    def _cell_reader(row):
        def cell(index: int, default: str = "") -> str:
            return row[index].strip() if len(row) > index else default

        return cell
