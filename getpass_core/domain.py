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


def phone_digits(value: str | None) -> str:
    """Вернуть до десяти цифр российского номера без кода страны."""
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("8"):
        digits = digits[1:]
    elif digits.startswith("7"):
        digits = digits[1:]
    return digits[:10]


def format_phone(value: str | None) -> str:
    """Форматировать ввод телефона как +7 (XXX) XXX-XX-XX."""
    digits = phone_digits(value)
    chunks = [digits[:3], digits[3:6], digits[6:8], digits[8:10]]
    result = "+7"
    if chunks[0]:
        result += " (" + chunks[0]
    if len(digits) >= 3:
        result += ")"
    if chunks[1]:
        result += " " + chunks[1]
    if chunks[2]:
        result += "-" + chunks[2]
    if chunks[3]:
        result += "-" + chunks[3]
    return result if digits else ""


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