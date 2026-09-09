"""Чистая предметная логика: даты, номера бланков, госномера."""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import datetime

DATE_FMT = "%d.%m.%Y"


def add_months_safe(sourcedate: datetime, months: int) -> datetime:
    month = sourcedate.month - 1 + months
    year = sourcedate.year + month // 12
    month = month % 12 + 1
    day = min(sourcedate.day, calendar.monthrange(year, month)[1])
    return sourcedate.replace(year=year, month=month, day=day)


def add_years_safe(sourcedate: datetime, years: int) -> datetime:
    try:
        return sourcedate.replace(year=sourcedate.year + years)
    except ValueError:
        return sourcedate.replace(year=sourcedate.year + years, day=28)


def parse_date(date_str: str | None) -> datetime | None:
    clean = (date_str or "").strip()
    if not clean:
        return None
    try:
        return datetime.strptime(clean, DATE_FMT)
    except ValueError:
        return None


def is_blank_date(date_str: str | None) -> bool:
    return not (date_str or "").strip()


def format_date(d: datetime) -> str:
    return d.strftime(DATE_FMT)


def is_active_on(valid_until: str | None, today) -> bool | None:
    d = parse_date(valid_until)
    if d is None:
        return None
    return d.date() >= today


@dataclass(frozen=True)
class NumberResult:
    value: str
    overflowed: bool = False
    incremented: bool = False


def next_number(code_str: str | None) -> NumberResult:
    if not code_str or not code_str.strip():
        return NumberResult("001-26", incremented=False)
    m = re.search(r"\d+", code_str)
    if m is None:
        return NumberResult(code_str, incremented=False)
    num_str = m.group()
    new_num = str(int(num_str) + 1)
    overflowed = len(new_num) > len(num_str)
    new_num = new_num.zfill(len(num_str))
    return NumberResult(
        code_str[: m.start()] + new_num + code_str[m.end():],
        overflowed=overflowed,
        incremented=True,
    )


def increment_number(code_str: str | None) -> str:
    return next_number(code_str).value


_LAT_TO_CYR = str.maketrans({
    "A": "А", "B": "В", "E": "Е", "K": "К", "M": "М", "H": "Н",
    "O": "О", "P": "Р", "C": "С", "T": "Т", "Y": "У", "X": "Х",
})


def normalize_plate(plate_raw: str | None) -> str:
    p = (plate_raw or "").strip().upper()
    p = "".join(p.split())
    return p.translate(_LAT_TO_CYR)


def plate_key(plate_raw: str | None) -> str:
    return normalize_plate(plate_raw)


_PLATE_PATTERNS = (
    (re.compile(r"^([А-Я])(\d{3})([А-Я]{2})(\d{2,3})$"), "{0}  {1}  {2}   {3}"),
    (re.compile(r"^([А-Я]{2})(\d{4})(\d{2,3})$"), "{0}  {1}   {2}"),
    (re.compile(r"^(\d{4})([А-Я]{2})(\d{2,3})$"), "{0}  {1}   {2}"),
    (re.compile(r"^([А-Я]{2})(\d{3})(\d{2,3})$"), "{0}  {1}   {2}"),
)


def format_plate_visual(plate_raw: str | None) -> str:
    p = normalize_plate(plate_raw)
    for pattern, tmpl in _PLATE_PATTERNS:
        m = pattern.match(p)
        if m:
            return tmpl.format(*m.groups())
    return p


def get_excel_col_letter(idx: int) -> str:
    result = ""
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        result = chr(65 + rem) + result
    return result


def join_fio(surname: str, name: str, patronymic: str) -> str:
    return " ".join(p for p in (surname, name, patronymic) if p).strip()


# Алиас для обратной совместимости
split_fio = join_fio