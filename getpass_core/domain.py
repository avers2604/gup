"""Чистая предметная логика: даты, номера бланков, госномера.

Модуль намеренно не импортирует ни tkinter, ни PIL — его можно импортировать
и тестировать без GUI и без графической подсистемы.
"""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import datetime

DATE_FMT = "%d.%m.%Y"

# ------------------------------------------------------------------ даты

def add_months_safe(sourcedate: datetime, months: int) -> datetime:
    """Прибавить месяцы, не вылетая на 31-х числах (31.01 + 1 мес -> 28/29.02)."""
    month = sourcedate.month - 1 + months
    year = sourcedate.year + month // 12
    month = month % 12 + 1
    day = min(sourcedate.day, calendar.monthrange(year, month)[1])
    return sourcedate.replace(year=year, month=month, day=day)


def add_years_safe(sourcedate: datetime, years: int) -> datetime:
    """Прибавить годы, корректно обрабатывая 29 февраля."""
    try:
        return sourcedate.replace(year=sourcedate.year + years)
    except ValueError:
        return sourcedate.replace(year=sourcedate.year + years, day=28)


def parse_date(date_str: str | None) -> datetime | None:
    """Разобрать ДД.ММ.ГГГГ. Возвращает None и для пустой, и для битой строки."""
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
    """Действителен ли пропуск на дату `today`.

    Возвращает None, если срок не указан или не разбирается — такие записи
    НЕ считаются действующими молча, вызывающий код обязан решить явно.
    """
    d = parse_date(valid_until)
    if d is None:
        return None
    return d.date() >= today


# ------------------------------------------------- номера бланков

@dataclass(frozen=True)
class NumberResult:
    value: str
    overflowed: bool = False
    incremented: bool = False


def next_number(code_str: str | None) -> NumberResult:
    """Увеличить числовую часть номера бланка на единицу.

    Инкрементируется ПЕРВАЯ группа цифр — в принятом формате «001-26» это
    порядковый номер, а «26» год выпуска бланка. Порядок групп менять нельзя:
    в формате «2026-001» увеличится год, а не номер.

    Если разрядность переполняется ('999' -> '1000'), это отмечается флагом,
    чтобы интерфейс мог предупредить оператора, а не менять формат молча.
    """
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
    """Совместимая обёртка: только строка результата."""
    return next_number(code_str).value


# ------------------------------------------------------- госномера

# Буквы, допустимые в российских госномерах, и их латинские двойники.
_LAT_TO_CYR = str.maketrans({
    "A": "А", "B": "В", "E": "Е", "K": "К", "M": "М", "H": "Н",
    "O": "О", "P": "Р", "C": "С", "T": "Т", "Y": "У", "X": "Х",
})


def normalize_plate(plate_raw: str | None) -> str:
    """Привести госномер к канону: верхний регистр, кириллица, без пробелов.

    Латинские двойники (O777TB198) и кириллица (О777ТВ198) выглядят одинаково,
    но дают разные ключи в базе. Нормализация делает их одной машиной.
    """
    p = (plate_raw or "").strip().upper()
    p = "".join(p.split())
    return p.translate(_LAT_TO_CYR)


def plate_key(plate_raw: str | None) -> str:
    """Ключ для базы автомобилей и поиска дублей."""
    return normalize_plate(plate_raw)


# Форматы: обычный, прицеп/мото, транзит, такси/спецтранспорт.
_PLATE_PATTERNS = (
    # Х 999 ХХ 99(9) — легковой/грузовой
    (re.compile(r"^([А-Я])(\d{3})([А-Я]{2})(\d{2,3})$"), "{0}  {1}  {2}   {3}"),
    # ХХ 9999 99(9) — прицеп
    (re.compile(r"^([А-Я]{2})(\d{4})(\d{2,3})$"), "{0}  {1}   {2}"),
    # 9999 ХХ 99(9) — мотоцикл
    (re.compile(r"^(\d{4})([А-Я]{2})(\d{2,3})$"), "{0}  {1}   {2}"),
    # ХХ 999 99(9) — такси/общественный
    (re.compile(r"^([А-Я]{2})(\d{3})(\d{2,3})$"), "{0}  {1}   {2}"),
)


def format_plate_visual(plate_raw: str | None) -> str:
    """Разрядка госномера для печати на бланке.

    Нераспознанный формат возвращается как есть (в верхнем регистре) —
    печатать что-то нужно в любом случае.
    """
    p = normalize_plate(plate_raw)
    for pattern, tmpl in _PLATE_PATTERNS:
        m = pattern.match(p)
        if m:
            return tmpl.format(*m.groups())
    return (plate_raw or "").strip().upper()


# ------------------------------------------------------------ прочее

def get_excel_col_letter(idx: int) -> str:
    """1 -> A, 27 -> AA."""
    result = ""
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        result = chr(65 + rem) + result
    return result


def split_fio(surname: str, name: str, patronymic: str) -> str:
    return " ".join(p for p in (surname, name, patronymic) if p).strip()
