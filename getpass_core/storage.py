"""Журналы пропусков: единая реализация для ТС и для работников.

Заменяет две почти одинаковые пары функций (чтение/запись/экспорт), которые
раньше жили отдельно и успели разойтись по багам.
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import uuid
import xml.sax.saxutils as saxutils
import zipfile
from dataclasses import dataclass, field
from datetime import datetime

from . import config
from .domain import DATE_FMT, get_excel_col_letter, parse_date, plate_key

STATUS_ACTIVE = "действует"
STATUS_REVOKED = "аннулирован"


class FileBusy(Exception):
    """Файл журнала занят другой программой (обычно открыт в Excel)."""

    def __init__(self, path: str):
        super().__init__(path)
        self.path = path


@dataclass(frozen=True)
class Field:
    key: str
    title: str
    width: int
    tree_width: int = 120
    anchor: str = "w"


@dataclass
class JournalSchema:
    name: str
    csv_path: str
    xlsx_path: str
    fields: tuple[Field, ...]
    # ключевое поле для поиска дублей (госномер / табельный номер)
    dup_key: str = ""
    #: как читать записи старых версий: длина строки -> список ключей
    legacy_layouts: dict = field(default_factory=dict)

    @property
    def keys(self) -> list[str]:
        return [f.key for f in self.fields]

    @property
    def header(self) -> list[str]:
        return [f.title for f in self.fields]

    @property
    def cols_def(self) -> list[tuple[str, int]]:
        return [(f.title, f.width) for f in self.fields]


_AUDIT_FIELDS = (
    Field("status", "Статус", 16, 100, "center"),
    Field("revoked_at", "Аннулирован", 16, 95, "center"),
    Field("revoke_reason", "Причина", 30, 160, "w"),
    Field("operator", "Оформил", 26, 140, "w"),
)

PASS_SCHEMA = JournalSchema(
    name="Журнал пропусков ТС",
    csv_path=config.LOG_CSV_FILE,
    xlsx_path=config.LOG_XLSX_FILE,
    dup_key="plate",
    fields=(
        Field("id", "ID", 14, 0, "w"),
        Field("num", "Номер пропуска", 18, 95, "center"),
        Field("plate", "Номер машины", 18, 110, "center"),
        Field("zone", "Зона допуска", 26, 150, "w"),
        Field("driver", "Водитель", 40, 240, "w"),
        Field("phone", "Телефон", 20, 130, "center"),
        Field("issue_date", "Дата выдачи", 16, 85, "center"),
        Field("valid_until", "Действителен до", 16, 85, "center"),
    ) + _AUDIT_FIELDS,
    legacy_layouts={
        6: ["num", "plate", "zone", "driver", "issue_date", "valid_until"],
        7: ["num", "plate", "zone", "driver", "phone", "issue_date", "valid_until"],
    },
)

BADGE_SCHEMA = JournalSchema(
    name="Журнал постоянных бейджей",
    csv_path=config.BADGE_LOG_CSV,
    xlsx_path=config.BADGE_LOG_XLSX,
    dup_key="tab_num",
    fields=(
        Field("id", "ID", 14, 0, "w"),
        Field("tab_num", "Табельный номер", 18, 105, "center"),
        Field("fio", "ФИО сотрудника", 38, 240, "w"),
        Field("role", "Должность", 28, 180, "w"),
        Field("park", "Подразделение", 32, 200, "w"),
        Field("phone", "Телефон", 18, 120, "center"),
        Field("issue_date", "Дата выдачи", 16, 85, "center"),
        Field("valid_until", "Действителен до", 16, 85, "center"),
    ) + _AUDIT_FIELDS,
    legacy_layouts={
        7: ["tab_num", "fio", "role", "park", "phone", "issue_date", "valid_until"],
    },
)


def new_id() -> str:
    return uuid.uuid4().hex[:12]


# --------------------------------------------------------------- XLSX

def export_records_to_xlsx(rows, cols_def, filepath, sheet_name="Журнал"):
    """Минимальный писатель XLSX без внешних зависимостей."""
    sheet_xml = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
        '  <cols>',
    ]
    for i, (_, width) in enumerate(cols_def, start=1):
        sheet_xml.append(f'    <col min="{i}" max="{i}" width="{width}" customWidth="1"/>')
    sheet_xml.append('  </cols>')
    sheet_xml.append('  <sheetData>')
    sheet_xml.append('    <row r="1">')
    for i, (name, _) in enumerate(cols_def):
        letter = get_excel_col_letter(i + 1)
        sheet_xml.append(
            f'      <c r="{letter}1" t="inlineStr"><is><t>{saxutils.escape(name)}</t></is></c>')
    sheet_xml.append('    </row>')
    for r_idx, row_data in enumerate(rows, start=2):
        sheet_xml.append(f'    <row r="{r_idx}">')
        for c_idx in range(len(cols_def)):
            val = str(row_data[c_idx]) if c_idx < len(row_data) else ""
            letter = get_excel_col_letter(c_idx + 1)
            sheet_xml.append(
                f'      <c r="{letter}{r_idx}" t="inlineStr">'
                f'<is><t>{saxutils.escape(val)}</t></is></c>')
        sheet_xml.append('    </row>')
    sheet_xml.append('  </sheetData>')
    sheet_xml.append('</worksheet>')
    sheet_str = "\n".join(sheet_xml)
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
        '  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
        '  <Default Extension="xml" ContentType="application/xml"/>\n'
        '  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>\n'
        '  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>\n'
        '</Types>'
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        '  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>\n'
        '</Relationships>'
    )
    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        '  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>\n'
        '</Relationships>'
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">\n'
        '  <sheets>\n'
        f'    <sheet name="{saxutils.escape(sheet_name)}" sheetId="1" r:id="rId1"/>\n'
        '  </sheets>\n'
        '</workbook>'
    )
    tmp = filepath + ".tmp"
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_str)
    os.replace(tmp, filepath)


# ------------------------------------------------------------ журнал

class Journal:
    """Журнал выдачи. Одна реализация для пропусков ТС и для бейджей."""

    def __init__(self, schema: JournalSchema):
        self.schema = schema

    # ---- чтение

    def read(self) -> list[dict]:
        path = self.schema.csv_path
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as f:
                rows = list(csv.reader(f, delimiter=";"))
        except Exception:
            return []
        if len(rows) < 2:
            return []
        header, body = rows[0], rows[1:]
        keys = self._keys_for(header)
        records = []
        for raw in body:
            if not any((c or "").strip() for c in raw):
                continue
            rec = {k: "" for k in self.schema.keys}
            layout = keys or self.schema.legacy_layouts.get(len(raw))
            if layout is None:
                layout = self.schema.keys
            for i, key in enumerate(layout):
                if key in rec and i < len(raw):
                    rec[key] = (raw[i] or "").strip()
            if not rec.get("id"):
                rec["id"] = new_id()
            if not rec.get("status"):
                rec["status"] = STATUS_ACTIVE
            records.append(rec)
        return records

    def _keys_for(self, header) -> list[str] | None:
        """Сопоставить заголовок файла с ключами схемы (по названиям колонок)."""
        titles = {f.title.strip().lower(): f.key for f in self.schema.fields}
        mapped, hits = [], 0
        for cell in header:
            key = titles.get((cell or "").strip().lower())
            mapped.append(key or "")
            hits += bool(key)
        return mapped if hits >= max(2, len(header) // 2) else None

    # ---- запись

    def write(self, records: list[dict]) -> None:
        """Атомарно переписать журнал. Бросает FileBusy, если файл занят."""
        rows = [[rec.get(k, "") for k in self.schema.keys] for rec in records]
        os.makedirs(os.path.dirname(self.schema.csv_path) or ".", exist_ok=True)
        for path in (self.schema.csv_path, self.schema.xlsx_path):
            if os.path.exists(path):
                try:
                    shutil.copy2(path, path + ".bak")
                except Exception:
                    pass
        self._write_csv(rows)
        self._write_xlsx(rows)

    def _write_csv(self, rows) -> None:
        path = self.schema.csv_path
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(self.schema.header)
                writer.writerows(rows)
            os.replace(tmp, path)
        except PermissionError as exc:
            raise FileBusy(path) from exc

    def _write_xlsx(self, rows) -> None:
        path = self.schema.xlsx_path
        try:
            export_records_to_xlsx(rows, self.schema.cols_def, path, self.schema.name)
        except PermissionError as exc:
            raise FileBusy(path) from exc

    # ---- операции

    def append_many(self, new_records: list[dict]) -> list[dict]:
        """Дописать пачку записей ОДНОЙ перезаписью файла (а не N перезаписями)."""
        current = self.read()
        for rec in new_records:
            prepared = {k: "" for k in self.schema.keys}
            prepared.update({k: v for k, v in rec.items() if k in prepared})
            prepared["id"] = prepared.get("id") or new_id()
            prepared["status"] = prepared.get("status") or STATUS_ACTIVE
            current.append(prepared)
        self.write(current)
        return current

    def delete_ids(self, ids) -> list[dict]:
        ids = set(ids)
        current = [r for r in self.read() if r.get("id") not in ids]
        self.write(current)
        return current

    def revoke_ids(self, ids, reason: str, when: str = "") -> list[dict]:
        """Аннулировать записи, сохранив их в истории (вместо удаления)."""
        ids = set(ids)
        when = when or datetime.now().strftime(DATE_FMT)
        current = self.read()
        for rec in current:
            if rec.get("id") in ids and rec.get("status") != STATUS_REVOKED:
                rec["status"] = STATUS_REVOKED
                rec["revoked_at"] = when
                rec["revoke_reason"] = reason
        self.write(current)
        return current

    def update_record(self, rec_id: str, values: dict) -> list[dict]:
        current = self.read()
        for rec in current:
            if rec.get("id") == rec_id:
                rec.update({k: v for k, v in values.items() if k in rec})
        self.write(current)
        return current

    # ---- выборки

    def active(self, records=None, today=None):
        """Действующие, просроченные и записи без внятного срока — раздельно."""
        records = self.read() if records is None else records
        today = today or datetime.now().date()
        live, expired, unknown = [], [], []
        for rec in records:
            if rec.get("status") == STATUS_REVOKED:
                expired.append(rec)
                continue
            d = parse_date(rec.get("valid_until"))
            if d is None:
                unknown.append(rec)
            elif d.date() >= today:
                live.append(rec)
            else:
                expired.append(rec)
        return live, expired, unknown

    def find_duplicates(self, value: str, today=None, exclude_id: str = "") -> list[dict]:
        """Действующие записи с тем же ключом (госномер / табельный номер)."""
        if not self.schema.dup_key or not (value or "").strip():
            return []
        norm = self._norm_key(value)
        live, _, unknown = self.active(today=today)
        out = []
        for rec in live + unknown:
            if rec.get("id") == exclude_id:
                continue
            if self._norm_key(rec.get(self.schema.dup_key, "")) == norm:
                out.append(rec)
        return out

    def _norm_key(self, value: str) -> str:
        if self.schema.dup_key == "plate":
            return plate_key(value)
        return "".join((value or "").upper().split())


PASS_JOURNAL = Journal(PASS_SCHEMA)
BADGE_JOURNAL = Journal(BADGE_SCHEMA)


# --------------------------------------------------- база автомобилей

def load_cars_cache() -> dict:
    if os.path.exists(config.CARS_CACHE_FILE):
        try:
            with open(config.CARS_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def save_cars_cache(cache: dict) -> None:
    try:
        os.makedirs(config.DATA_DIR, exist_ok=True)
        tmp = config.CARS_CACHE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        os.replace(tmp, config.CARS_CACHE_FILE)
    except Exception:
        pass


def update_cars_cache(car_infos) -> None:
    """Обновить базу пачкой: одно чтение и одна запись на весь список."""
    if isinstance(car_infos, dict):
        car_infos = [car_infos]
    cache = load_cars_cache()
    changed = False
    for car in car_infos:
        key = plate_key(car.get("plate"))
        if not key:
            continue
        cache[key] = {
            "brand": car.get("brand", ""), "model": car.get("model", ""),
            "type": car.get("type", ""), "color": car.get("color", ""),
            "d_pos": car.get("d_pos", ""), "d_fio": car.get("d_fio", ""),
            "d_phone": car.get("phone", ""), "territory": car.get("territory", ""),
        }
        changed = True
    if changed:
        save_cars_cache(cache)


def lookup_car(plate: str) -> dict | None:
    return load_cars_cache().get(plate_key(plate))


def export_journal(journal, filepath: str) -> int:
    """Выгрузить журнал в отдельный файл XLSX или CSV. Возвращает число записей."""
    records = journal.read()
    schema = journal.schema
    rows = [[rec.get(k, "") for k in schema.keys] for rec in records]
    if filepath.lower().endswith(".csv"):
        with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(schema.header)
            writer.writerows(rows)
    else:
        export_records_to_xlsx(rows, schema.cols_def, filepath, schema.name)
    return len(records)
