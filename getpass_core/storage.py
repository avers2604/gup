"""Журналы пропусков: единая реализация для ТС и для работников."""
from __future__ import annotations

import csv
import json
import os
import re
import sqlite3
import uuid
import xml.sax.saxutils as saxutils
import zipfile
from dataclasses import dataclass, field
from datetime import datetime

from . import config
from .domain import DATE_FMT, get_excel_col_letter, parse_date, plate_key

STATUS_ACTIVE = "действует"
STATUS_REVOKED = "аннулирован"

_XML_ILLEGAL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


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
    table: str = ""
    dup_key: str = ""
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
    Field("status", "Статус", 16, 115, "center"),
    Field("revoked_at", "Аннулирован", 16, 120, "center"),
    Field("revoke_reason", "Причина", 30, 160, "w"),
)

PASS_SCHEMA = JournalSchema(
    name="Журнал пропусков ТС",
    csv_path=config.LOG_CSV_FILE,
    xlsx_path=config.LOG_XLSX_FILE,
    table="pass_journal",
    dup_key="plate",
    fields=(
        Field("id", "ID", 14, 0, "w"),
        Field("num", "Номер пропуска", 18, 95, "center"),
        Field("plate", "Номер машины", 18, 110, "center"),
        Field("zone", "Зона допуска", 26, 150, "w"),
        Field("driver", "Водитель", 40, 240, "w"),
        Field("phone", "Телефон", 20, 130, "center"),
        Field("issue_date", "Дата выдачи", 16, 105, "center"),
        Field("valid_until", "Действителен до", 16, 135, "center"),
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
    table="badge_journal",
    dup_key="tab_num",
    fields=(
        Field("id", "ID", 14, 0, "w"),
        Field("tab_num", "Табельный номер", 18, 105, "center"),
        Field("fio", "ФИО сотрудника", 38, 240, "w"),
        Field("role", "Должность", 28, 180, "w"),
        Field("park", "Подразделение", 32, 200, "w"),
        Field("phone", "Телефон", 18, 120, "center"),
        Field("issue_date", "Дата выдачи", 16, 105, "center"),
        Field("valid_until", "Действителен до", 16, 135, "center"),
        Field("photo_path", "Фото", 40, 0, "w"),
    ) + _AUDIT_FIELDS,
    legacy_layouts={
        7: ["tab_num", "fio", "role", "park", "phone", "issue_date", "valid_until"],
    },
)


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def _clean_xml(val: str) -> str:
    cleaned = _XML_ILLEGAL_CHARS.sub("", str(val))
    return saxutils.escape(cleaned)


def export_records_to_xlsx(rows, cols_def, filepath, sheet_name="Журнал"):
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
            f'      <c r="{letter}1" t="inlineStr"><is><t>{_clean_xml(name)}</t></is></c>')
    sheet_xml.append('    </row>')
    for r_idx, row_data in enumerate(rows, start=2):
        sheet_xml.append(f'    <row r="{r_idx}">')
        for c_idx in range(len(cols_def)):
            val = row_data[c_idx] if c_idx < len(row_data) else ""
            letter = get_excel_col_letter(c_idx + 1)
            sheet_xml.append(
                f'      <c r="{letter}{r_idx}" t="inlineStr">'
                f'<is><t>{_clean_xml(val)}</t></is></c>')
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
        f'    <sheet name="{_clean_xml(sheet_name)}" sheetId="1" r:id="rId1"/>\n'
        '  </sheets>\n'
        '</workbook>'
    )
    tmp = filepath + ".tmp"
    try:
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("[Content_Types].xml", content_types)
            zf.writestr("_rels/.rels", rels)
            zf.writestr("xl/_rels/workbook.xml.rels", wb_rels)
            zf.writestr("xl/workbook.xml", workbook)
            zf.writestr("xl/worksheets/sheet1.xml", sheet_str)
        os.replace(tmp, filepath)
    except PermissionError as exc:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass
        raise FileBusy(filepath) from exc


class Journal:
    """Журнал выдачи на базе SQLite."""

    def __init__(self, schema: JournalSchema):
        self.schema = schema

    def _connect(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(config.DB_FILE) or ".", exist_ok=True)
        try:
            conn = sqlite3.connect(config.DB_FILE, timeout=10)
        except sqlite3.OperationalError as exc:
            raise FileBusy(config.DB_FILE) from exc

        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA busy_timeout = 10000")

        self._ensure_table(conn)
        return conn

    def _ensure_table(self, conn: sqlite3.Connection) -> None:
        table = self.schema.table
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if exists:
            return
        cols = ", ".join(f'"{k}" TEXT' for k in self.schema.keys)
        conn.execute(f'CREATE TABLE "{table}" ({cols}, PRIMARY KEY ("id"))')
        legacy = self._read_legacy_csv()
        if legacy:
            self._insert_all(conn, legacy)
        conn.commit()

    def _insert_all(self, conn: sqlite3.Connection, records: list[dict]) -> None:
        cols = self.schema.keys
        col_list = ", ".join(f'"{k}"' for k in cols)
        placeholders = ", ".join("?" for _ in cols)
        conn.executemany(
            f'INSERT INTO "{self.schema.table}" ({col_list}) VALUES ({placeholders})',
            [tuple(rec.get(k, "") for k in cols) for rec in records],
        )

    def _read_legacy_csv(self) -> list[dict]:
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
        titles = {f.title.strip().lower(): f.key for f in self.schema.fields}
        mapped, hits = [], 0
        for cell in header:
            key = titles.get((cell or "").strip().lower())
            mapped.append(key or "")
            hits += bool(key)
        return mapped if hits >= max(2, len(header) // 2) else None

    def read(self) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(f'SELECT * FROM "{self.schema.table}" ORDER BY rowid ASC').fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def write(self, records: list[dict]) -> None:
        """Перезаписать журнал в рамках одной транзакции."""
        conn = self._connect()
        try:
            with conn:
                conn.execute(f'DELETE FROM "{self.schema.table}"')
                self._insert_all(conn, records)
        except sqlite3.OperationalError as exc:
            raise FileBusy(config.DB_FILE) from exc
        finally:
            conn.close()

    def append_many(self, new_records: list[dict]) -> list[dict]:
        """Дописать пачку записей через единый вызов write()."""
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
        id_set = set(ids)
        current = [r for r in self.read() if r.get("id") not in id_set]
        self.write(current)
        return current

    def revoke_ids(self, ids, reason: str, when: str = "") -> list[dict]:
        id_set = set(ids)
        when = when or datetime.now().strftime(DATE_FMT)
        current = self.read()
        for rec in current:
            if rec.get("id") in id_set and rec.get("status") != STATUS_REVOKED:
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

    def active(self, records=None, today=None):
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

    def distinct(self, key: str, records=None) -> list[str]:
        records = self.read() if records is None else records
        values = {(rec.get(key) or "").strip() for rec in records}
        values.discard("")
        return sorted(values, key=str.lower)


PASS_JOURNAL = Journal(PASS_SCHEMA)
BADGE_JOURNAL = Journal(BADGE_SCHEMA)


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
    if isinstance(car_infos, dict):
        car_infos = [car_infos]
    cache = load_cars_cache()
    changed = False
    for car in car_infos:
        key = plate_key(car.get("plate"))
        if not key:
            continue
        existing = cache.get(key, {})
        incoming = {
            "brand": car.get("brand", ""), "model": car.get("model", ""),
            "type": car.get("type", ""), "color": car.get("color", ""),
            "d_pos": car.get("d_pos", ""), "d_fio": car.get("d_fio", ""),
            "d_phone": car.get("phone", ""), "territory": car.get("territory", ""),
        }
        cache[key] = {k: (v or existing.get(k, "")) for k, v in incoming.items()}
        changed = True
    if changed:
        save_cars_cache(cache)


def lookup_car(plate: str) -> dict | None:
    return load_cars_cache().get(plate_key(plate))


def known_car_brands() -> list[str]:
    values = {(car.get("brand") or "").strip() for car in load_cars_cache().values()}
    values.discard("")
    return sorted(values, key=str.lower)


def export_journal(journal, filepath: str) -> int:
    records = journal.read()
    schema = journal.schema
    rows = [[rec.get(k, "") for k in schema.keys] for rec in records]
    if filepath.lower().endswith(".csv"):
        try:
            with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(schema.header)
                writer.writerows(rows)
        except PermissionError as exc:
            raise FileBusy(filepath) from exc
    else:
        export_records_to_xlsx(rows, schema.cols_def, filepath, schema.name)
    return len(records)