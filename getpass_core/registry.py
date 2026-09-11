"""Печатные реестры. Одна реализация вместо двух почти одинаковых функций."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from PIL import Image, ImageDraw

from .fonts import get_echoes_font, get_styled_font
from .pdfwriter import write_pdf
from .render import _fit_text, draw_dot_icon

PAGE_W, PAGE_H = 2480, 3508
ROWS_PER_PAGE = 23

C_NAVY = "#0A2540"
C_RED = "#C62828"


@dataclass(frozen=True)
class RegColumn:
    key: str
    title: str
    width: int
    align: str = "center"        # center | left
    style: str = "normal"        # normal | bold | plate | until
    icon_when: str = ""          # подстрока в значении -> пиктограмма слева


@dataclass(frozen=True)
class RegistrySpec:
    title: str
    columns: tuple[RegColumn, ...]
    count_label: str             # «Активных ТС» / «Активных работников»


PASS_REGISTRY = RegistrySpec(
    title="РЕЕСТР ТС ДЛЯ ПЕЧАТИ",
    count_label="Активных ТС",
    columns=(
        RegColumn("_idx", "№", 90),
        RegColumn("num", "№ Пропуска", 260, style="bold"),
        RegColumn("plate", "Гос. номер", 380, style="plate"),
        RegColumn("zone", "Зона допуска", 360, icon_when="парков"),
        RegColumn("driver", "Водитель", 490, align="left"),
        RegColumn("phone", "Телефон", 340, style="bold"),
        RegColumn("valid_until", "Действителен", 280, style="until"),
    ),
)

BADGE_REGISTRY = RegistrySpec(
    title="РЕЕСТР ДЕЙСТВУЮЩИХ ПРОПУСКОВ РАБОТНИКОВ",
    count_label="Активных работников",
    columns=(
        RegColumn("_idx", "№", 90),
        RegColumn("tab_num", "Таб. №", 230, style="bold"),
        RegColumn("fio", "ФИО сотрудника", 550, align="left", style="bold"),
        RegColumn("role", "Должность", 430, align="left"),
        RegColumn("park", "Подразделение", 410),
        RegColumn("phone", "Телефон", 270, style="bold"),
        RegColumn("valid_until", "Действителен", 220, style="until"),
    ),
)


def build_registry_pages(records, spec: RegistrySpec, total_in_base: int,
                         today_str: str = "", progress=None):
    """Собрать страницы реестра. Возвращает генератор изображений."""
    today_str = today_str or datetime.now().strftime("%d.%m.%Y")
    pages_data = [records[i:i + ROWS_PER_PAGE] for i in range(0, len(records), ROWS_PER_PAGE)]
    total_pages = max(1, len(pages_data))

    font_h1 = get_echoes_font(56, bold=True)
    font_h2 = get_echoes_font(36, bold=True)
    font_meta = get_echoes_font(32)
    font_td = get_echoes_font(32)
    font_td_bold = get_echoes_font(34, bold=True)
    font_td_plate = get_styled_font("plate", 36)
    font_page = get_echoes_font(28)

    table_x = 140
    table_w = sum(c.width for c in spec.columns)
    item_idx = 1

    for page_idx, page_rows in enumerate(pages_data or [[]], start=1):
        img = Image.new("RGB", (PAGE_W, PAGE_H), "white")
        draw = ImageDraw.Draw(img)
        draw.text((PAGE_W // 2, 140), "СПБ ГУП «ГОРЭЛЕКТРОТРАНС»", fill=C_NAVY,
                  font=font_h1, anchor="mm")
        draw.text((PAGE_W // 2, 220), spec.title, fill="#1B2126", font=font_h2, anchor="mm")
        draw_dot_icon(draw, "tram", table_x + 40, 140, C_RED, size=64, anchor="mm")
        draw_dot_icon(draw, "trol", table_x + table_w - 40, 140, "#009FA0", size=64, anchor="mm")
        draw.text((table_x, 295), f"Дата формирования: {today_str}", fill="#5A6872",
                  font=font_meta, anchor="ls")
        draw.text((table_x + table_w, 295),
                  f"{spec.count_label}: {len(records)} из {total_in_base}",
                  fill="#5A6872", font=font_meta, anchor="rs")

        th_y, th_h = 335, 95
        draw.rectangle([table_x, th_y, table_x + table_w, th_y + th_h], fill=C_NAVY)
        curr_x = table_x
        for col in spec.columns:
            # Безопасная посадка заголовка столбца
            _fit_text(draw, col.title, curr_x + col.width // 2, th_y + th_h // 2,
                      col.width - 16, 34, anchor="mm", fill="white", bold=True)
            curr_x += col.width

        tr_y, tr_h = th_y + th_h, 105
        for row_idx, rec in enumerate(page_rows):
            draw.rectangle([table_x, tr_y, table_x + table_w, tr_y + tr_h],
                           fill="#F6F8FA" if row_idx % 2 else "#FFFFFF")
            curr_x = table_x
            mid_y = tr_y + tr_h // 2
            for col in spec.columns:
                value = str(item_idx) if col.key == "_idx" else str(rec.get(col.key, "") or "")
                _draw_cell(draw, col, value, curr_x, mid_y,
                           font_td, font_td_bold, font_td_plate)
                curr_x += col.width
            draw.line([(table_x, tr_y + tr_h), (table_x + table_w, tr_y + tr_h)],
                      fill="#D6DEE4", width=2)
            tr_y += tr_h
            item_idx += 1

        draw.rectangle([table_x, th_y, table_x + table_w, tr_y], outline=C_NAVY, width=3)
        vert_x = table_x
        for col in spec.columns[:-1]:
            vert_x += col.width
            draw.line([(vert_x, th_y), (vert_x, tr_y)], fill="#D6DEE4", width=2)
        draw.text((PAGE_W // 2, 3420), f"Страница {page_idx} из {total_pages}",
                  fill="#777777", font=font_page, anchor="mm")
        if progress:
            try:
                progress(page_idx, total_pages)
            except Exception:
                pass
        yield img


def _draw_cell(draw, col, value, curr_x, mid_y, font_td, font_td_bold, font_td_plate):
    if col.key == "_idx":
        draw.text((curr_x + col.width // 2, mid_y), value, fill="#666666",
                  font=font_td, anchor="mm")
        return
    if col.style == "plate":
        draw.text((curr_x + col.width // 2, mid_y), value, fill="#000000",
                  font=font_td_plate, anchor="mm")
        return
    if col.style == "until":
        draw.text((curr_x + col.width // 2, mid_y), f"до {value}" if value else "—",
                  fill=C_RED, font=font_td_bold, anchor="mm")
        return

    bold = (col.style == "bold")
    size = 34 if bold else 32

    if col.icon_when and col.icon_when in value.lower():
        draw_dot_icon(draw, "p", curr_x + 40, mid_y, C_NAVY, size=44, anchor="mm")
        _fit_text(draw, value, curr_x + 78, mid_y, col.width - 100, size,
                  anchor="lm", bold=bold)
        return

    if col.align == "left":
        _fit_text(draw, value, curr_x + 20, mid_y, col.width - 35, size,
                  anchor="lm", bold=bold)
    else:
        _fit_text(draw, value, curr_x + col.width // 2, mid_y, col.width - 30, size,
                  anchor="mm", bold=bold)


def save_registry_pdf(records, spec, total_in_base, filepath, progress=None):
    """Записать реестр в PDF, не держа все страницы в памяти одновременно."""
    pages = build_registry_pages(records, spec, total_in_base, progress=progress)
    return write_pdf(pages, filepath, dpi=300)
