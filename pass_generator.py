import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageDraw, ImageFont, ImageTk
import os
import sys
import subprocess
import re
import json
import csv
import zipfile
import shutil
import traceback
import calendar
import ctypes
import xml.sax.saxutils as saxutils
from datetime import datetime

# ============================================================
# ПУТИ
# ============================================================
if getattr(sys, 'frozen', False):
    SCRIPT_DIR = os.path.dirname(sys.executable)
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(SCRIPT_DIR, "settings.json")
LOG_CSV_FILE = os.path.join(SCRIPT_DIR, "журнал_пропусков.csv")
LOG_XLSX_FILE = os.path.join(SCRIPT_DIR, "журнал_пропусков.xlsx")
BADGE_LOG_CSV = os.path.join(SCRIPT_DIR, "журнал_бейджей.csv")
BADGE_LOG_XLSX = os.path.join(SCRIPT_DIR, "журнал_бейджей.xlsx")
CARS_CACHE_FILE = os.path.join(SCRIPT_DIR, "cars_database.json")
ICON_FILE = os.path.join(SCRIPT_DIR, "app_icon.ico")
TEMPLATE_FILE = os.path.join(SCRIPT_DIR, "template.png")
CRASH_LOG_FILE = os.path.join(SCRIPT_DIR, "crash.log")
FONTS_DIR = os.path.join(SCRIPT_DIR, "fonts")

# ============================================================
# ОБРАБОТЧИК КРИТИЧЕСКИХ ОШИБОК
# ============================================================
def global_exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    try:
        with open(CRASH_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.now().strftime('%d.%m.%Y %H:%M:%S')}] CRASH:\n{err_msg}\n")
    except Exception:
        pass
    try:
        messagebox.showerror("Критическая ошибка", f"Ошибка:\n{exc_value}\n\nДетали в crash.log")
    except Exception:
        pass

sys.excepthook = global_exception_handler

# ============================================================
# ДАТЫ
# ============================================================
def add_months_safe(sourcedate, months):
    month = sourcedate.month - 1 + months
    year = sourcedate.year + month // 12
    month = month % 12 + 1
    day = min(sourcedate.day, calendar.monthrange(year, month)[1])
    return sourcedate.replace(year=year, month=month, day=day)

def add_years_safe(sourcedate, years):
    try:
        return sourcedate.replace(year=sourcedate.year + years)
    except ValueError:
        return sourcedate.replace(year=sourcedate.year + years, day=28)

def validate_date_string(date_str, field_name):
    clean = (date_str or "").strip()
    if not clean:
        return None
    try:
        return datetime.strptime(clean, "%d.%m.%Y")
    except ValueError:
        messagebox.showwarning("Некорректная дата", f"Поле «{field_name}»: «{date_str}»\nФормат: ДД.ММ.ГГГГ")
        return None

# ============================================================
# ШРИФТЫ БЛАНКОВ (С КЭШЕМ)
# ============================================================
_FONT_CACHE = {}

def get_styled_font(style_type, size):
    key = (style_type, size)
    cached = _FONT_CACHE.get(key)
    if cached is not None:
        return cached
    candidates = {
        "title": ["GOTHICB.TTF", "gothicb.ttf", "segoeuib.ttf", "LiberationSans-Bold.ttf", "arialbd.ttf"],
        "plate": ["bahnschrift.ttf", "trebucbd.ttf", "LiberationSans-Bold.ttf", "arialbd.ttf"],
        "geo": ["GOTHICB.TTF", "gothicb.ttf", "segoeuib.ttf", "LiberationSans-Bold.ttf"],
        "geo_reg": ["GOTHIC.TTF", "gothic.ttf", "segoeui.ttf", "LiberationSans-Regular.ttf", "arial.ttf"],
        "body": ["segoeuib.ttf", "calibrib.ttf", "LiberationSans-Bold.ttf", "arialbd.ttf"],
        "light": ["segoeui.ttf", "calibri.ttf", "LiberationSans-Regular.ttf", "arial.ttf"]
    }
    font = ImageFont.load_default()
    for name in candidates.get(style_type, ["arialbd.ttf"]):
        try:
            font = ImageFont.truetype(name, size)
            break
        except IOError:
            continue
    _FONT_CACHE[key] = font
    return font

def draw_auto_fit_text(draw, text, x, y, max_w, max_size, min_size=16, font_style="body", fill="#1b2126", anchor="mm", **kwargs):
    if not text:
        return
    size = max_size
    while size > min_size:
        f = get_styled_font(font_style, size)
        bbox = draw.textbbox((0, 0), text, font=f)
        if (bbox[2] - bbox[0]) <= max_w:
            break
        size -= 2
    font = get_styled_font(font_style, size)
    draw.text((x, y), text, fill=fill, font=font, anchor=anchor)

def format_plate_visual(plate_raw):
    p = (plate_raw or "").strip().upper()
    m = re.match(r'^([А-ЯA-Z])\s*(\d{3})\s*([А-ЯA-Z]{2})\s*(\d{2,3})$', p)
    if m:
        return f"{m.group(1)}  {m.group(2)}  {m.group(3)}   {m.group(4)}"
    return p

# ============================================================
# БРЕНДБУК: ECHOES SANS
#   ✅ интерфейс, ✅ реестры   ❌ пропуск ТС   ❌ бейдж
# ============================================================
_ECHOES_REGULAR = None
_ECHOES_BOLD = None
_ECHOES_FOUND = False
UI_FAMILY = "Segoe UI"

ECHOES_NAMES_REG = ["echoes sans.ttf", "echoessans.ttf", "echoes_sans.ttf", "echoessans-regular.ttf",
                    "echoes sans regular.ttf", "echoessansregular.ttf", "echoessans-regular.otf", "echoes sans.otf"]
ECHOES_NAMES_BOLD = ["echoes sans bold.ttf", "echoessans-bold.ttf", "echoessansbold.ttf", "echoes_sans_bold.ttf",
                     "echoessans-semibold.ttf", "echoes sans semibold.ttf"]

def find_echoes_font():
    global _ECHOES_REGULAR, _ECHOES_BOLD, _ECHOES_FOUND
    if _ECHOES_FOUND:
        return
    _ECHOES_FOUND = True
    search_dirs = [SCRIPT_DIR, FONTS_DIR]
    if os.name == "nt":
        windir = os.environ.get("WINDIR", r"C:\Windows")
        search_dirs.append(os.path.join(windir, "Fonts"))
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            search_dirs.append(os.path.join(local, "Microsoft", "Windows", "Fonts"))
    for d in search_dirs:
        if not d or not os.path.isdir(d):
            continue
        try:
            files = os.listdir(d)
        except Exception:
            continue
        low_map = {f.lower(): f for f in files}
        for name in ECHOES_NAMES_REG:
            if name in low_map and _ECHOES_REGULAR is None:
                _ECHOES_REGULAR = os.path.join(d, low_map[name])
        for name in ECHOES_NAMES_BOLD:
            if name in low_map and _ECHOES_BOLD is None:
                _ECHOES_BOLD = os.path.join(d, low_map[name])
        for f in files:
            fl = f.lower()
            if "echoes" in fl and fl.endswith((".ttf", ".otf")):
                full = os.path.join(d, f)
                is_bold = any(k in fl for k in ("bold", "semibold", "-sb", "_sb"))
                if is_bold and _ECHOES_BOLD is None:
                    _ECHOES_BOLD = full
                elif not is_bold and _ECHOES_REGULAR is None:
                    _ECHOES_REGULAR = full
        if _ECHOES_REGULAR:
            break

def get_echoes_font(size, bold=False):
    find_echoes_font()
    path = _ECHOES_BOLD if bold else _ECHOES_REGULAR
    if path is None and bold:
        path = _ECHOES_REGULAR
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return get_styled_font("geo" if bold else "geo_reg", size)

def setup_ui_font():
    global UI_FAMILY
    find_echoes_font()
    if _ECHOES_REGULAR and os.name == "nt":
        try:
            family = ImageFont.truetype(_ECHOES_REGULAR, 20).getname()[0]
            ok = bool(ctypes.windll.gdi32.AddFontResourceW(_ECHOES_REGULAR))
            if _ECHOES_BOLD:
                ctypes.windll.gdi32.AddFontResourceW(_ECHOES_BOLD)
            if ok:
                UI_FAMILY = family
        except Exception:
            UI_FAMILY = "Segoe UI"
    return UI_FAMILY

def F(size, bold=False, italic=False):
    style = ("bold " if bold else "") + ("italic" if italic else "")
    style = style.strip()
    return (UI_FAMILY, size, style) if style else (UI_FAMILY, size)

# ============================================================
# DoT ICONS: пиктограммы для PDF-документов (лигатуры через RAQM)
#   ✅ шапки реестров, ✅ зона «Парковка», ✅ листы массовой печати
#   ❌ интерфейс Tkinter (нет шейпинга)   ❌ пропуск ТС   ❌ бейдж
# ============================================================
DOT_ICON_CANDIDATES = ["DoT Icons.ttf", "DoTIcons.ttf", "dot_icons.ttf", "doticons-regular.ttf", "dot icons regular.ttf"]
_DOT_ICON_PATH = None
_DOT_ICON_PATH_SEARCHED = False
_DOT_FONT_CACHE = {}
_RAQM_OK = None

def find_dot_icons_font():
    global _DOT_ICON_PATH, _DOT_ICON_PATH_SEARCHED
    if _DOT_ICON_PATH_SEARCHED:
        return _DOT_ICON_PATH
    _DOT_ICON_PATH_SEARCHED = True
    for d in (FONTS_DIR, SCRIPT_DIR):
        if not d or not os.path.isdir(d):
            continue
        try:
            files = os.listdir(d)
        except Exception:
            continue
        low = {f.lower(): f for f in files}
        for name in DOT_ICON_CANDIDATES:
            if name in low:
                _DOT_ICON_PATH = os.path.join(d, low[name])
                return _DOT_ICON_PATH
        for f in files:
            fl = f.lower()
            if "dot" in fl and "icon" in fl and fl.endswith((".ttf", ".otf")):
                _DOT_ICON_PATH = os.path.join(d, f)
                return _DOT_ICON_PATH
    return _DOT_ICON_PATH

def raqm_ok():
    global _RAQM_OK
    if _RAQM_OK is None:
        try:
            from PIL import features
            _RAQM_OK = bool(features.check("raqm"))
        except Exception:
            _RAQM_OK = False
    return _RAQM_OK

def get_dot_icons_font(size):
    if size in _DOT_FONT_CACHE:
        return _DOT_FONT_CACHE[size]
    path = find_dot_icons_font()
    if not path:
        return None
    kw = {"layout_engine": ImageFont.LAYOUT_RAQM} if raqm_ok() else {}
    try:
        f = ImageFont.truetype(path, size, **kw)
    except TypeError:
        f = ImageFont.truetype(path, size)
    except Exception:
        f = None
    _DOT_FONT_CACHE[size] = f
    return f

def draw_dot_icon(draw, code, x, y, color, size=48, anchor="mm", bg_code=None, bg_color="#FFFFFF"):
    """Пиктограмма DoT Icons. bg_code — подложка (o/O/d/D) другим цветом."""
    f = get_dot_icons_font(size)
    if f is None:
        return False
    if bg_code:
        draw.text((x, y), bg_code, fill=bg_color, font=f, anchor=anchor)
    draw.text((x, y), code, fill=color, font=f, anchor=anchor)
    return True

def draw_sheet_brand_icons(draw, x, y, size=48, color_tram="#C62828", color_trol="#009FA0"):
    """Пара tram+trol — фирменный знак ГЭТ в строке заголовка листа."""
    ok1 = draw_dot_icon(draw, "tram", x, y, color_tram, size=size, anchor="lm")
    ok2 = draw_dot_icon(draw, "trol", x + int(size * 1.5), y, color_trol, size=size, anchor="lm")
    return ok1 or ok2

def render_dot_icons_test_sheet():
    """Тестовый лист: визуально проверить коды пиктограмм."""
    if not find_dot_icons_font():
        messagebox.showwarning("Шрифт не найден",
                               "Положите файл DoT Icons.ttf в папку:\n" + FONTS_DIR +
                               "\n\nБез него пиктограммы просто не рисуются (программа работает штатно).")
        return
    codes = ["tram", "trol", "p", "no", "b", "left", "right", "up", "down", "back",
             "pl", "pr", "1", "7", "11a", "o8", "o8a", "o1", "o11a", "O2", "d1", "Dd1",
             "o2", "o20", "x1", "x20", "tram21", "trol7"]
    img = Image.new("RGB", (2480, 1560), "#FFFFFF")
    draw = ImageDraw.Draw(img)
    draw.text((1240, 90), "DoT Icons — тестовый лист кодов (ГЭТ)", fill="#0A2540",
              font=get_echoes_font(56, bold=True), anchor="mm")
    if not raqm_ok():
        draw.text((1240, 170), "ВНИМАНИЕ: Pillow собран без RAQM — составные лигатуры могут не собраться",
                  fill="#C62828", font=get_echoes_font(34, bold=True), anchor="mm")
    x, y = 160, 300
    for code in codes:
        drawn = draw_dot_icon(draw, code, x + 70, y + 60, "#D32F2F", size=90)
        draw.text((x + 160, y + 60), code if drawn else f"{code}  (нет шрифта)",
                  fill="#1B2126", font=get_echoes_font(34), anchor="lm")
        x += 760
        if x > 2200:
            x = 160
            y += 210
    path = os.path.join(SCRIPT_DIR, "test_DoT_Icons.png")
    img.save(path)
    messagebox.showinfo("Готово", f"Тестовый лист сохранён:\n{path}")
    try:
        os.startfile(path)
    except Exception:
        pass

# ============================================================
# БАЗА АВТОМОБИЛЕЙ
# ============================================================
def load_cars_cache():
    if os.path.exists(CARS_CACHE_FILE):
        try:
            with open(CARS_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def update_cars_cache(car_info):
    cache = load_cars_cache()
    key = "".join((car_info.get("plate") or "").upper().split())
    if key:
        cache[key] = {
            "brand": car_info.get("brand", ""), "model": car_info.get("model", ""),
            "type": car_info.get("type", ""), "color": car_info.get("color", ""),
            "d_pos": car_info.get("d_pos", ""), "d_fio": car_info.get("d_fio", ""),
            "d_phone": car_info.get("phone", ""), "territory": car_info.get("territory", "")
        }
        try:
            with open(CARS_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

def auto_complete_car_fields(plate_var, brand_ent, model_ent, type_ent, color_ent, pos_ent, fio_ent, phone_ent, territory_cb):
    raw_plate = plate_var.get().strip().upper()
    key = "".join(raw_plate.split())
    if not key:
        return
    cache = load_cars_cache()
    if key in cache:
        car = cache[key]
        filled = False
        if not brand_ent.get().strip(): brand_ent.insert(0, car.get("brand", "")); filled = True
        if not model_ent.get().strip(): model_ent.insert(0, car.get("model", "")); filled = True
        if not type_ent.get().strip(): type_ent.insert(0, car.get("type", "")); filled = True
        if not color_ent.get().strip(): color_ent.insert(0, car.get("color", "")); filled = True
        if not pos_ent.get().strip(): pos_ent.insert(0, car.get("d_pos", "")); filled = True
        if not fio_ent.get().strip(): fio_ent.insert(0, car.get("d_fio", "")); filled = True
        if not phone_ent.get().strip(): phone_ent.insert(0, car.get("d_phone", "")); filled = True
        if not territory_cb.get().strip(): territory_cb.set(car.get("territory", "")); filled = True
        if filled:
            schedule_auto_preview()

# ============================================================
# НАСТРОЙКИ
# ============================================================
def increment_number(code_str):
    if not code_str:
        return "001-26"
    match = re.search(r'\d+', code_str)
    if not match:
        return code_str
    num_str = match.group()
    new_num = str(int(num_str) + 1).zfill(len(num_str))
    return code_str[:match.start()] + new_num + code_str[match.end():]

def load_settings():
    defaults = {
        "last_pass_num": "001-26",
        "territory": 'ПТО "Шаврова"',
        "otb_post": "", "otb_name": "",
        "valid_until": "31.12.2026",
        "is_temporary_car": False, "print_mode": "a4",
        "badge_park": "ОСП «Трамвайный парк № 8»",
        "badge_tab_num": "01035",
        "badge_print_mode": "card",
        "last_printer": "По умолчанию",
        "auto_preview_target": "1"
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                defaults.update(json.load(f))
        except Exception:
            pass
    defaults["issue_date"] = datetime.now().strftime("%d.%m.%Y")
    return defaults

def save_settings():
    try:
        data = {
            "last_pass_num": p1_num.get().strip() or settings.get("last_pass_num", "001-26"),
            "territory": p1_territory.get().strip() or settings.get("territory", ""),
            "otb_post": entry_otb_post.get().strip(),
            "otb_name": entry_otb_name.get().strip(),
            "valid_until": entry_valid.get().strip() or settings.get("valid_until", "31.12.2026"),
            "is_temporary_car": is_temp_car_var.get(),
            "print_mode": print_mode_var.get(),
            "badge_park": badge_park_cb.get().strip(),
            "badge_tab_num": b_tab_num_ent.get().strip() or settings.get("badge_tab_num", "01035"),
            "badge_print_mode": badge_print_mode_var.get(),
            "last_printer": printer_var.get(),
            "auto_preview_target": auto_preview_target.get()
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception:
        pass

# ============================================================
# XLSX / CSV
# ============================================================
def get_excel_col_letter(idx):
    result = ""
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        result = chr(65 + rem) + result
    return result

def export_records_to_xlsx(records, cols_def, filepath, sheet_name="Журнал"):
    sheet_xml = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
        '  <cols>'
    ]
    for i, (_, width) in enumerate(cols_def, start=1):
        sheet_xml.append(f'    <col min="{i}" max="{i}" width="{width}" customWidth="1"/>')
    sheet_xml.append('  </cols>')
    sheet_xml.append('  <sheetData>')
    sheet_xml.append('    <row r="1">')
    for i, (name, _) in enumerate(cols_def):
        letter = get_excel_col_letter(i + 1)
        sheet_xml.append(f'      <c r="{letter}1" t="inlineStr"><is><t>{saxutils.escape(name)}</t></is></c>')
    sheet_xml.append('    </row>')
    for r_idx, row_data in enumerate(records, start=2):
        sheet_xml.append(f'    <row r="{r_idx}">')
        for c_idx in range(len(cols_def)):
            val = str(row_data[c_idx]) if c_idx < len(row_data) else ""
            letter = get_excel_col_letter(c_idx + 1)
            sheet_xml.append(f'      <c r="{letter}{r_idx}" t="inlineStr"><is><t>{saxutils.escape(val)}</t></is></c>')
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
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">\n'
        f'  <sheets>\n'
        f'    <sheet name="{saxutils.escape(sheet_name)}" sheetId="1" r:id="rId1"/>\n'
        f'  </sheets>\n'
        f'</workbook>'
    )
    with zipfile.ZipFile(filepath, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('[Content_Types].xml', content_types)
        zf.writestr('_rels/.rels', rels)
        zf.writestr('xl/_rels/workbook.xml.rels', wb_rels)
        zf.writestr('xl/workbook.xml', workbook)
        zf.writestr('xl/worksheets/sheet1.xml', sheet_str)

def safe_write_csv_xlsx(csv_path, xlsx_path, header, cols_def, records, sheet_name):
    if os.path.exists(csv_path):
        try:
            shutil.copy2(csv_path, csv_path + ".bak")
        except Exception:
            pass
    while True:
        try:
            with open(csv_path, mode="w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(header)
                writer.writerows(records)
            break
        except PermissionError:
            if not messagebox.askretrycancel("Файл занят", f"«{os.path.basename(csv_path)}» открыт в другой программе.\nЗакройте и нажмите «Повторить»."):
                return False
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить CSV: {e}")
            return False
    while True:
        try:
            export_records_to_xlsx(records, cols_def, xlsx_path, sheet_name)
            break
        except PermissionError:
            if not messagebox.askretrycancel("Файл занят", f"«{os.path.basename(xlsx_path)}» открыт в Excel.\nЗакройте и нажмите «Повторить»."):
                return False
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить XLSX: {e}")
            return False
    return True

PASS_COLS_DEF = [("Номер пропуска", 18), ("Номер машины", 18), ("Зона допуска", 26), ("Водитель", 40),
                 ("Телефон", 20), ("Дата выдачи", 16), ("Действителен до", 16)]
PASS_HEADER = ["Номер пропуска", "Номер машины", "Зона допуска", "Водитель", "Телефон", "Дата выдачи", "Действителен до"]
BADGE_COLS_DEF = [("Табельный номер", 18), ("ФИО сотрудника", 38), ("Должность", 28), ("Подразделение", 32),
                  ("Телефон", 18), ("Дата выдачи", 16), ("Действителен до", 16)]
BADGE_HEADER = ["Табельный номер", "ФИО сотрудника", "Должность", "Подразделение", "Телефон", "Дата выдачи", "Действителен до"]

def read_log_records():
    records = []
    if os.path.exists(LOG_CSV_FILE):
        try:
            with open(LOG_CSV_FILE, mode="r", encoding="utf-8-sig") as f:
                rows = list(csv.reader(f, delimiter=";"))
                if len(rows) > 1:
                    for r in rows[1:]:
                        if len(r) == 6:
                            records.append([r[0], r[1], r[2], r[3], "", r[4], r[5]])
                        elif len(r) >= 7:
                            records.append(r[:7])
        except Exception:
            pass
    return records

def safe_write_log_records(records):
    return safe_write_csv_xlsx(LOG_CSV_FILE, LOG_XLSX_FILE, PASS_HEADER, PASS_COLS_DEF, records, "Журнал пропусков ТС")

def add_passes_to_log(passes_list):
    current = read_log_records()
    for p in passes_list:
        current.append([p["num"], (p["plate"] or "").upper(), p.get("territory") or "Основная (Без зоны)",
                        p.get("driver_full", ""), p.get("phone", ""), p["issue_date"], p["valid_until"]])
        update_cars_cache(p)
    safe_write_log_records(current)

def read_badge_log_records():
    records = []
    if os.path.exists(BADGE_LOG_CSV):
        try:
            with open(BADGE_LOG_CSV, mode="r", encoding="utf-8-sig") as f:
                rows = list(csv.reader(f, delimiter=";"))
                if len(rows) > 1:
                    records = [r[:7] for r in rows[1:]]
        except Exception:
            pass
    return records

def safe_write_badge_log_records(records):
    return safe_write_csv_xlsx(BADGE_LOG_CSV, BADGE_LOG_XLSX, BADGE_HEADER, BADGE_COLS_DEF, records, "Журнал постоянных бейджей")

def add_badge_to_log(badge_info):
    current = read_badge_log_records()
    current.append([badge_info["tab_num"], badge_info["fio"], badge_info["role"], badge_info["park"],
                    badge_info.get("phone", ""), badge_info["issue_date"], badge_info["valid_until"]])
    safe_write_badge_log_records(current)

# ============================================================
# БЛАНКИ (КЭШ)
# ============================================================
_CACHED_BASE_TEMPLATE = None
_CACHED_BADGE_LOGO = None

def get_base_template(silent=False):
    global _CACHED_BASE_TEMPLATE
    target_w, target_h = 2480, 1560
    if os.path.exists(TEMPLATE_FILE):
        try:
            if _CACHED_BASE_TEMPLATE is None:
                im = Image.open(TEMPLATE_FILE).convert("RGB")
                _CACHED_BASE_TEMPLATE = im.resize((target_w, target_h), Image.Resampling.LANCZOS)
            return _CACHED_BASE_TEMPLATE.copy()
        except Exception as e:
            if not silent:
                messagebox.showerror("Ошибка", f"Не удалось прочитать template.png:\n{e}")
    else:
        if not silent:
            messagebox.showerror("Файл не найден", f"Положите template.png в папку программы:\n{SCRIPT_DIR}")
    return Image.new("RGB", (target_w, target_h), "#ffffff")

def get_badge_logo_img(target_width=340):
    global _CACHED_BADGE_LOGO
    if _CACHED_BADGE_LOGO is None:
        base_tpl = get_base_template()
        _CACHED_BADGE_LOGO = base_tpl.crop((60, 65, 890, 260))
    aspect = _CACHED_BADGE_LOGO.height / _CACHED_BADGE_LOGO.width
    target_h = int(target_width * aspect)
    return _CACHED_BADGE_LOGO.resize((target_width, target_h), Image.Resampling.LANCZOS)

# ============================================================
# БЕЙДЖ 85×54 (ОТРИСОВКА НЕ ИЗМЕНЕНА)
# ============================================================
CARD_W, CARD_H = 638, 1004

def fit_photo_to_box(photo_path, target_w, target_h):
    im = Image.open(photo_path).convert("RGB")
    orig_w, orig_h = im.size
    scale = max(target_w / orig_w, target_h / orig_h)
    new_w, new_h = int(orig_w * scale), int(orig_h * scale)
    resized = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))

def render_single_badge_image(badge_data, silent=False):
    badge = Image.new("RGB", (CARD_W, CARD_H), "#FFFFFF")
    draw = ImageDraw.Draw(badge)
    C_NAVY = "#0A2540"; C_TEXT = "#1B2126"
    badge.paste(get_badge_logo_img(target_width=340), (25, 20))
    draw_auto_fit_text(draw, badge_data.get("park", ""), CARD_W // 2, 142, 590, 32, min_size=18, font_style="body", fill=C_NAVY, anchor="mm")
    draw_auto_fit_text(draw, badge_data.get("role", ""), CARD_W // 2, 182, 590, 32, min_size=18, font_style="body", fill=C_TEXT, anchor="mm")
    pw, ph = 582, 560
    photo_path = badge_data.get("photo_path")
    if photo_path and os.path.exists(photo_path):
        try:
            badge.paste(fit_photo_to_box(photo_path, pw, ph), (28, 215))
        except Exception:
            draw.rectangle([28, 215, 28 + pw, 215 + ph], fill="#F0F4F8")
    else:
        draw.rectangle([28, 215, 28 + pw, 215 + ph], fill="#F0F4F8")
        draw.text((CARD_W // 2, 215 + ph // 2), "ФОТОГРАФИЯ СОТРУДНИКА", fill="#9AA5B1",
                  font=get_styled_font("body", 28), anchor="mm", align="center")
    draw.rectangle([28, 215, 28 + pw, 215 + ph], outline="#CBD2D9", width=1)
    draw_auto_fit_text(draw, (badge_data.get("surname") or "").upper(), CARD_W // 2, 825, 580, 38, min_size=18, font_style="body", fill="#000000", anchor="mm")
    draw_auto_fit_text(draw, (badge_data.get("name") or "").upper(), CARD_W // 2, 870, 580, 38, min_size=18, font_style="body", fill="#000000", anchor="mm")
    draw_auto_fit_text(draw, (badge_data.get("patronymic") or "").upper(), CARD_W // 2, 915, 580, 38, min_size=18, font_style="body", fill="#000000", anchor="mm")
    date_str = f"с {badge_data.get('issue_date', '')} по {badge_data.get('valid_until', '')}"
    draw.text((28, 970), date_str, fill="#1B2126", font=get_styled_font("light", 24), anchor="ls")
    draw.text((CARD_W - 28, 970), badge_data.get("tab_num", ""), fill=C_NAVY, font=get_styled_font("title", 42), anchor="rs")
    return badge

def build_a4_sheet_of_badges(badge_img, count=9):
    a4_sheet = Image.new("RGB", (2480, 3508), "#FFFFFF")
    draw_a4 = ImageDraw.Draw(a4_sheet)
    cols, rows = 3, 3
    total_w = cols * CARD_W; total_h = rows * CARD_H
    start_x = (2480 - total_w) // 2; start_y = (3508 - total_h) // 2
    for r in range(rows):
        for c in range(cols):
            x = start_x + c * CARD_W; y = start_y + r * CARD_H
            a4_sheet.paste(badge_img, (x, y))
            draw_a4.rectangle([x, y, x + CARD_W, y + CARD_H], outline="#A0AEC0", width=2)
    draw_a4.text((1240, start_y - 60), "СПБ ГУП «ГОРЭЛЕКТРОТРАНС» — ЛИСТ ПЕЧАТИ ПРОПУСКОВ РАБОТНИКОВ (85 × 54 мм)",
                 fill="#718096", font=get_styled_font("light", 32), anchor="mm")
    draw_sheet_brand_icons(draw_a4, 150, start_y - 60, size=44)
    return a4_sheet

# ============================================================
# ПРОПУСК НА ТС (ОТРИСОВКА НЕ ИЗМЕНЕНА)
# ============================================================
def render_pass(pass_data, common_data, silent=False):
    base_img = get_base_template(silent=silent)
    target_w, target_h = base_img.size
    img = base_img.copy()
    draw = ImageDraw.Draw(img)
    C_NAVY = "#0A2540"; C_TEXT = "#1B2126"; C_RED = "#C62828"; C_SIGNAL_RED = "#D32F2F"
    if common_data.get("is_temporary"):
        draw.rectangle([500, 345, 1950, 425], fill="#ffffff")
        font_title = get_styled_font("title", 74)
        title_str = "ВРЕМЕННЫЙ  ПРОПУСК  №"
        num_str = pass_data["num"]
        full_str = f"{title_str}  {num_str}"
        total_w = draw.textlength(full_str, font=font_title)
        start_x = (target_w - total_w) // 2
        w_title = draw.textlength(title_str + "  ", font=font_title)
        draw.text((start_x, 410), title_str, fill="#181a30", font=font_title, anchor="ls")
        draw.text((start_x + w_title, 410), num_str, fill=C_NAVY, font=font_title, anchor="ls")
    else:
        draw.text((1400, 410), pass_data["num"], fill=C_NAVY, font=get_styled_font("title", 76), anchor="ls")
    if pass_data.get("territory"):
        draw_auto_fit_text(draw, pass_data["territory"].upper(), x=1240, y=452, max_w=1400, max_size=36,
                           min_size=20, font_style="geo", fill=C_NAVY, anchor="mm")
    else:
        draw.rectangle([70, 438, target_w - 70, 464], fill=C_SIGNAL_RED)
    draw_auto_fit_text(draw, format_plate_visual(pass_data.get("plate", "")), x=1240, y=558, max_w=1700,
                       max_size=145, min_size=55, font_style="plate", fill="#000000", anchor="mm")
    draw_auto_fit_text(draw, pass_data.get("brand", ""), 680, 775, max_w=800, max_size=64, min_size=24, font_style="body", fill=C_TEXT, anchor="mm")
    draw_auto_fit_text(draw, pass_data.get("model", ""), 680, 965, max_w=800, max_size=64, min_size=24, font_style="body", fill=C_TEXT, anchor="mm")
    draw_auto_fit_text(draw, pass_data.get("type", ""), 1860, 775, max_w=800, max_size=64, min_size=24, font_style="body", fill=C_TEXT, anchor="mm")
    draw_auto_fit_text(draw, pass_data.get("color", ""), 1860, 965, max_w=800, max_size=64, min_size=24, font_style="body", fill=C_TEXT, anchor="mm")
    draw_auto_fit_text(draw, pass_data.get("driver_full", ""), x=1240, y=1195, max_w=1850, max_size=58,
                       min_size=26, font_style="body", fill=C_TEXT, anchor="ms")
    draw_auto_fit_text(draw, common_data.get("otb_post", ""), x=440, y=1420, max_w=650, max_size=48, min_size=22, font_style="body", fill=C_TEXT, anchor="ms")
    draw_auto_fit_text(draw, common_data.get("otb_name", ""), x=1917, y=1420, max_w=650, max_size=54, min_size=24, font_style="body", fill=C_TEXT, anchor="ms")
    f_d_lbl = get_styled_font("geo_reg", 36); f_d_val = get_styled_font("title", 46); f_d_exp = get_styled_font("title", 54)
    draw.text((1940, 150), "ВЫДАН:", fill="#626577", font=f_d_lbl, anchor="lm")
    draw.text((2120, 150), common_data.get('issue_date', ''), fill=C_NAVY, font=f_d_val, anchor="lm")
    draw.line([(1920, 202), (2335, 202)], fill="#CBD2D9", width=2)
    draw.text((1940, 260), "ДО:", fill=C_RED, font=f_d_lbl, anchor="lm")
    draw.text((2050, 260), common_data.get('valid_until', ''), fill=C_RED, font=f_d_exp, anchor="lm")
    return img

def _fit_text(draw, text, x, y, max_w, max_size, font_echoes=None, anchor="mm", fill="#000000"):
    if not text:
        return
    size = max_size
    font = font_echoes
    while size > 16:
        f = get_echoes_font(size)
        bbox = draw.textbbox((0, 0), text, font=f)
        if (bbox[2] - bbox[0]) <= max_w:
            font = f
            break
        size -= 2
    if font is None:
        font = get_echoes_font(size)
    draw.text((x, y), text, fill=fill, font=font, anchor=anchor)

# ============================================================
# РЕЕСТР ТС ДЛЯ ПЕЧАТИ  (Echoes Sans + DoT Icons)
# ============================================================
def generate_ts_registry_pdf():
    all_records = read_log_records()
    if not all_records:
        messagebox.showinfo("Реестр пуст", "В базе нет записей.")
        return
    today_date = datetime.now().date()
    records = []
    for r in all_records:
        valid_until_str = r[6].strip() if len(r) > 6 else ""
        try:
            if datetime.strptime(valid_until_str, "%d.%m.%Y").date() >= today_date:
                records.append(r)
        except Exception:
            records.append(r)
    if not records:
        messagebox.showinfo("Нет активных", "Все пропуска в базе просрочены на сегодняшнюю дату!")
        return
    today_str = datetime.now().strftime("%d.%m.%Y")
    filepath = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Документ", "*.pdf")],
                                            initialfile=f"Реестр_ТС_для_печати_{today_str}.pdf")
    if not filepath:
        return
    page_w, page_h = 2480, 3508
    rows_per_page = 23
    pages_data = [records[i:i + rows_per_page] for i in range(0, len(records), rows_per_page)]
    total_pages = len(pages_data)
    font_h1 = get_echoes_font(56, bold=True); font_h2 = get_echoes_font(36, bold=True)
    font_meta = get_echoes_font(32); font_th = get_echoes_font(34, bold=True)
    font_td = get_echoes_font(32); font_td_plate = get_styled_font("plate", 36)
    font_td_bold = get_echoes_font(34, bold=True); font_page = get_echoes_font(28)
    cols = [("№", 90), ("№ Пропуска", 260), ("Гос. номер", 380), ("Зона допуска", 360),
            ("Водитель", 490), ("Телефон", 340), ("Действителен", 280)]
    table_x = 140; table_w = sum(c[1] for c in cols)
    pdf_pages = []; global_item_idx = 1
    for page_idx, page_rows in enumerate(pages_data, start=1):
        img = Image.new("RGB", (page_w, page_h), "white"); draw = ImageDraw.Draw(img)
        draw.text((page_w // 2, 140), "СПБ ГУП «ГОРЭЛЕКТРОТРАНС»", fill="#0A2540", font=font_h1, anchor="mm")
        draw.text((page_w // 2, 220), "РЕЕСТР ТС ДЛЯ ПЕЧАТИ", fill="#1B2126", font=font_h2, anchor="mm")
        # фирменные пиктограммы по краям титула
        draw_dot_icon(draw, "tram", table_x + 40, 140, "#C62828", size=64, anchor="mm")
        draw_dot_icon(draw, "trol", table_x + table_w - 40, 140, "#009FA0", size=64, anchor="mm")
        draw.text((table_x, 295), f"Дата формирования: {today_str}", fill="#5A6872", font=font_meta, anchor="ls")
        draw.text((table_x + table_w, 295), f"Активных ТС: {len(records)} из {len(all_records)}", fill="#5A6872", font=font_meta, anchor="rs")
        th_y = 335; th_h = 95
        draw.rectangle([table_x, th_y, table_x + table_w, th_y + th_h], fill="#0A2540")
        curr_x = table_x
        for title, w in cols:
            draw.text((curr_x + w // 2, th_y + th_h // 2), title, fill="white", font=font_th, anchor="mm"); curr_x += w
        tr_y = th_y + th_h; tr_h = 105
        for row_idx, r in enumerate(page_rows):
            draw.rectangle([table_x, tr_y, table_x + table_w, tr_y + tr_h], fill="#F6F8FA" if row_idx % 2 else "#FFFFFF")
            curr_x = table_x
            draw.text((curr_x + cols[0][1] // 2, tr_y + tr_h // 2), str(global_item_idx), fill="#666666", font=font_td, anchor="mm"); curr_x += cols[0][1]
            draw.text((curr_x + cols[1][1] // 2, tr_y + tr_h // 2), str(r[0]), fill="#0A2540", font=font_td_bold, anchor="mm"); curr_x += cols[1][1]
            draw.text((curr_x + cols[2][1] // 2, tr_y + tr_h // 2), str(r[1]), fill="#000000", font=font_td_plate, anchor="mm"); curr_x += cols[2][1]
            zone_val = str(r[2])
            if "парков" in zone_val.lower():
                draw_dot_icon(draw, "p", curr_x + 40, tr_y + tr_h // 2, "#0A2540", size=44, anchor="mm")
                _fit_text(draw, zone_val, curr_x + 78, tr_y + tr_h // 2, cols[3][1] - 100, 32, font_echoes=font_td, anchor="lm")
            else:
                _fit_text(draw, zone_val, curr_x + cols[3][1] // 2, tr_y + tr_h // 2, cols[3][1] - 30, 32, font_echoes=font_td, anchor="mm")
            curr_x += cols[3][1]
            _fit_text(draw, str(r[3]), curr_x + 20, tr_y + tr_h // 2, cols[4][1] - 35, 32, font_echoes=font_td, anchor="lm"); curr_x += cols[4][1]
            phone_val = str(r[4]) if len(r) > 6 else ""
            _fit_text(draw, phone_val, curr_x + cols[5][1] // 2, tr_y + tr_h // 2, cols[5][1] - 20, 30, font_echoes=font_td_bold, anchor="mm"); curr_x += cols[5][1]
            valid_val = str(r[6]) if len(r) > 6 else (str(r[5]) if len(r) > 5 else "")
            draw.text((curr_x + cols[6][1] // 2, tr_y + tr_h // 2), f"до {valid_val}", fill="#C62828", font=font_td_bold, anchor="mm")
            draw.line([(table_x, tr_y + tr_h), (table_x + table_w, tr_y + tr_h)], fill="#D6DEE4", width=2)
            tr_y += tr_h; global_item_idx += 1
        draw.rectangle([table_x, th_y, table_x + table_w, tr_y], outline="#0A2540", width=3)
        vert_x = table_x
        for _, w in cols[:-1]:
            vert_x += w
            draw.line([(vert_x, th_y), (vert_x, tr_y)], fill="#D6DEE4", width=2)
        draw.text((page_w // 2, 3420), f"Страница {page_idx} из {total_pages}", fill="#777777", font=font_page, anchor="mm")
        pdf_pages.append(img)
    pdf_pages[0].save(filepath, "PDF", resolution=300.0, save_all=True, append_images=pdf_pages[1:])
    if messagebox.askyesno("Готово", f"Сформирован реестр ТС для печати ({len(records)} шт.)!\n\nОткрыть файл?"):
        try:
            os.startfile(filepath)
        except Exception:
            pass

# ============================================================
# РЕЕСТР РАБОТНИКОВ  (Echoes Sans + DoT Icons)
# ============================================================
def generate_employee_registry_pdf():
    all_records = read_badge_log_records()
    if not all_records:
        messagebox.showinfo("Реестр пуст", "В базе нет оформленных сотрудников.")
        return
    today_date = datetime.now().date()
    records = []
    for r in all_records:
        valid_until_str = r[6].strip() if len(r) > 6 else ""
        try:
            if datetime.strptime(valid_until_str, "%d.%m.%Y").date() >= today_date:
                records.append(r)
        except Exception:
            records.append(r)
    if not records:
        messagebox.showinfo("Нет активных", "Все пропуска работников просрочены!")
        return
    today_str = datetime.now().strftime("%d.%m.%Y")
    filepath = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Документ", "*.pdf")],
                                            initialfile=f"Реестр_работников_{today_str}.pdf")
    if not filepath:
        return
    page_w, page_h = 2480, 3508
    rows_per_page = 23
    pages_data = [records[i:i + rows_per_page] for i in range(0, len(records), rows_per_page)]
    total_pages = len(pages_data)
    font_h1 = get_echoes_font(56, bold=True); font_h2 = get_echoes_font(36, bold=True)
    font_meta = get_echoes_font(32); font_th = get_echoes_font(34, bold=True)
    font_td = get_echoes_font(32); font_td_bold = get_echoes_font(34, bold=True); font_page = get_echoes_font(28)
    cols = [("№", 90), ("Таб. №", 230), ("ФИО сотрудника", 550), ("Должность", 430),
            ("Подразделение", 410), ("Телефон", 270), ("Действителен", 220)]
    table_x = 140; table_w = sum(c[1] for c in cols)
    pdf_pages = []; global_item_idx = 1
    for page_idx, page_rows in enumerate(pages_data, start=1):
        img = Image.new("RGB", (page_w, page_h), "white"); draw = ImageDraw.Draw(img)
        draw.text((page_w // 2, 140), "СПБ ГУП «ГОРЭЛЕКТРОТРАНС»", fill="#0A2540", font=font_h1, anchor="mm")
        draw.text((page_w // 2, 220), "РЕЕСТР ДЕЙСТВУЮЩИХ ПРОПУСКОВ РАБОТНИКОВ", fill="#1B2126", font=font_h2, anchor="mm")
        draw_dot_icon(draw, "tram", table_x + 40, 140, "#C62828", size=64, anchor="mm")
        draw_dot_icon(draw, "trol", table_x + table_w - 40, 140, "#009FA0", size=64, anchor="mm")
        draw.text((table_x, 295), f"Дата формирования: {today_str}", fill="#5A6872", font=font_meta, anchor="ls")
        draw.text((table_x + table_w, 295), f"Активных работников: {len(records)} из {len(all_records)}", fill="#5A6872", font=font_meta, anchor="rs")
        th_y = 335; th_h = 95
        draw.rectangle([table_x, th_y, table_x + table_w, th_y + th_h], fill="#0A2540")
        curr_x = table_x
        for title, w in cols:
            draw.text((curr_x + w // 2, th_y + th_h // 2), title, fill="white", font=font_th, anchor="mm"); curr_x += w
        tr_y = th_y + th_h; tr_h = 105
        for row_idx, r in enumerate(page_rows):
            draw.rectangle([table_x, tr_y, table_x + table_w, tr_y + tr_h], fill="#F6F8FA" if row_idx % 2 else "#FFFFFF")
            curr_x = table_x
            draw.text((curr_x + cols[0][1] // 2, tr_y + tr_h // 2), str(global_item_idx), fill="#666666", font=font_td, anchor="mm"); curr_x += cols[0][1]
            draw.text((curr_x + cols[1][1] // 2, tr_y + tr_h // 2), str(r[0]), fill="#0A2540", font=font_td_bold, anchor="mm"); curr_x += cols[1][1]
            _fit_text(draw, str(r[1]), curr_x + 20, tr_y + tr_h // 2, cols[2][1] - 35, 32, font_echoes=font_td_bold, anchor="lm"); curr_x += cols[2][1]
            _fit_text(draw, str(r[2]), curr_x + 20, tr_y + tr_h // 2, cols[3][1] - 35, 30, font_echoes=font_td, anchor="lm"); curr_x += cols[3][1]
            _fit_text(draw, str(r[3]), curr_x + cols[4][1] // 2, tr_y + tr_h // 2, cols[4][1] - 30, 30, font_echoes=font_td, anchor="mm"); curr_x += cols[4][1]
            phone_val = str(r[4]) if len(r) > 4 else ""
            _fit_text(draw, phone_val, curr_x + cols[5][1] // 2, tr_y + tr_h // 2, cols[5][1] - 20, 30, font_echoes=font_td_bold, anchor="mm"); curr_x += cols[5][1]
            valid_val = str(r[6]) if len(r) > 6 else ""
            draw.text((curr_x + cols[6][1] // 2, tr_y + tr_h // 2), f"до {valid_val}", fill="#C62828", font=font_td_bold, anchor="mm")
            draw.line([(table_x, tr_y + tr_h), (table_x + table_w, tr_y + tr_h)], fill="#D6DEE4", width=2)
            tr_y += tr_h; global_item_idx += 1
        draw.rectangle([table_x, th_y, table_x + table_w, tr_y], outline="#0A2540", width=3)
        vert_x = table_x
        for _, w in cols[:-1]:
            vert_x += w
            draw.line([(vert_x, th_y), (vert_x, tr_y)], fill="#D6DEE4", width=2)
        draw.text((page_w // 2, 3420), f"Страница {page_idx} из {total_pages}", fill="#777777", font=font_page, anchor="mm")
        pdf_pages.append(img)
    pdf_pages[0].save(filepath, "PDF", resolution=300.0, save_all=True, append_images=pdf_pages[1:])
    if messagebox.askyesno("Готово", f"Сформирован реестр работников ({len(records)} чел.)!\n\nОткрыть файл?"):
        try:
            os.startfile(filepath)
        except Exception:
            pass

# ============================================================
# МАССОВАЯ ПЕЧАТЬ — ТС
# ============================================================
def export_batch_template():
    filepath = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")],
                                            initialfile="Шаблон_массовой_печати_ТС.csv")
    if filepath:
        with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["Номер пропуска", "Госномер", "Марка", "Модель", "Вид", "Цвет",
                             "Должность водителя", "ФИО водителя", "Телефон", "Зона допуска"])
            writer.writerow(["001-26", "О 777 ТВ 198", "ГАЗ", "Газель NEXT", "Служебный", "Белый",
                             "Водитель 1-го класса", "Смирнов А.В.", "+7 (921) 111-22-33", 'ПТО "Шаврова"'])
        messagebox.showinfo("Шаблон сохранен", f"Заполните файл в Excel:\n{filepath}")

def run_batch_print():
    batch_file = filedialog.askopenfilename(title="Массовая печать: выберите CSV со списком машин",
                                            filetypes=[("CSV", "*.csv"), ("Все файлы", "*.*")])
    if not batch_file:
        return
    items = []
    try:
        with open(batch_file, "r", encoding="utf-8-sig") as f:
            rows = list(csv.reader(f, delimiter=";"))
            if len(rows) > 1:
                for r in rows[1:]:
                    if len(r) >= 2 and r[1].strip():
                        items.append({
                            "num": r[0].strip(), "plate": r[1].strip(),
                            "brand": r[2].strip() if len(r) > 2 else "",
                            "model": r[3].strip() if len(r) > 3 else "",
                            "type": r[4].strip() if len(r) > 4 else "Служебный",
                            "color": r[5].strip() if len(r) > 5 else "",
                            "d_pos": r[6].strip() if len(r) > 6 else "",
                            "d_fio": r[7].strip() if len(r) > 7 else "",
                            "phone": r[8].strip() if len(r) > 8 else "",
                            "driver_full": f"{r[6].strip() if len(r) > 6 else ''} {r[7].strip() if len(r) > 7 else ''}".strip(),
                            "territory": r[9].strip() if len(r) > 9 else ""
                        })
    except Exception as e:
        messagebox.showerror("Ошибка чтения", f"Не удалось прочитать файл: {e}")
        return
    if not items:
        messagebox.showwarning("Пусто", "В файле нет записей.")
        return
    save_pdf_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
                                                 initialfile=f"Массовая_печать_ТС_{len(items)}шт.pdf")
    if not save_pdf_path:
        return
    common = {
        "issue_date": entry_issue.get().strip() or datetime.now().strftime("%d.%m.%Y"),
        "valid_until": entry_valid.get().strip() or settings.get("valid_until", "31.12.2026"),
        "otb_post": entry_otb_post.get().strip(),
        "otb_name": entry_otb_name.get().strip(),
        "is_temporary": is_temp_car_var.get()
    }
    p_win = tk.Toplevel(root); p_win.title("Массовая печать ТС"); p_win.geometry("420x130")
    p_win.transient(root); p_win.grab_set()
    lbl_p = ttk.Label(p_win, text="Подготовка документов...", font=F(10)); lbl_p.pack(pady=(15, 8))
    p_bar = ttk.Progressbar(p_win, length=340, mode="determinate"); p_bar.pack(pady=5)
    p_win.update()
    pdf_pages = []
    y_slot = 3508 // 2
    total_pairs = (len(items) + 1) // 2
    for pair_idx, i in enumerate(range(0, len(items), 2)):
        p1 = items[i]; img1 = render_pass(p1, common)
        p2 = items[i + 1] if (i + 1) < len(items) else p1
        img2 = render_pass(p2, common)
        a4_doc = Image.new("RGB", (2480, 3508), "white"); draw = ImageDraw.Draw(a4_doc)
        y_off1 = (y_slot - img1.height) // 2
        y_off2 = y_slot + (y_slot - img2.height) // 2
        a4_doc.paste(img1, (0, y_off1)); a4_doc.paste(img2, (0, y_off2))
        for x in range(120, 2360, 45):
            draw.line([(x, y_slot), (x + 25, y_slot)], fill="#9E9E9E", width=3)
        draw.text((1240, y_slot), "   ✂   ЛИНИЯ РАЗРЕЗА   ✂   ", fill="#757575", font=get_styled_font("geo", 36), anchor="mm")
        draw_sheet_brand_icons(draw, 140, 52, size=44)
        pdf_pages.append(a4_doc)
        p_bar["value"] = ((pair_idx + 1) / total_pairs) * 100
        lbl_p.config(text=f"Обработано {min(i + 2, len(items))} из {len(items)} пропусков...")
        p_win.update()
    pdf_pages[0].save(save_pdf_path, "PDF", resolution=300.0, save_all=True, append_images=pdf_pages[1:])
    add_passes_to_log([dict(it, **common) for it in items])
    p_win.destroy()
    if messagebox.askyesno("Успех", f"Массовая печать: {len(items)} пропусков готово!\n\nОткрыть файл?"):
        try:
            os.startfile(save_pdf_path)
        except Exception:
            pass

def open_batch_window():
    bwin = tk.Toplevel(root); bwin.title("Массовая печать пропусков на ТС")
    bwin.geometry("540x280"); bwin.transient(root); bwin.grab_set()
    f = ttk.Frame(bwin, padding="20"); f.pack(fill="both", expand=True)
    ttk.Label(f, text="МАССОВАЯ ПЕЧАТЬ пропусков из Excel / CSV", font=F(11, True)).pack(anchor="w", pady=(0, 10))
    ttk.Label(f, text="1. Скачайте шаблон таблицы и заполните список машин.\n"
                      "2. Выберите готовый файл для генерации единого PDF.", justify="left").pack(anchor="w", pady=(0, 15))
    tk.Button(f, text="📥 1. Скачать пустой шаблон (CSV)", command=export_batch_template,
              bg="#ECEFF1", font=F(10), pady=6, relief="groove", cursor="hand2").pack(fill="x", pady=4)
    tk.Button(f, text="🚀 2. Выбрать файл и напечатать массово", command=lambda: (bwin.destroy(), run_batch_print()),
              bg="#0A2540", fg="white", font=F(10, True), pady=8, relief="flat", cursor="hand2").pack(fill="x", pady=6)

# ============================================================
# МАССОВАЯ ПЕЧАТЬ — БЕЙДЖИ
# ============================================================
def export_badge_batch_template():
    filepath = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")],
                                            initialfile="Шаблон_массовой_печати_бейджей.csv")
    if filepath:
        with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["Табельный номер", "Фамилия", "Имя", "Отчество", "Должность", "Подразделение",
                             "Телефон", "Имя_файла_фото", "Дата выдачи", "Действителен до"])
            writer.writerow(["01035", "ИВАНОВ", "ИВАН", "ИВАНОВИЧ", "Водитель трамвая",
                             "ОСП «Трамвайный парк № 8»", "+7 (921) 123-45-67", "ivanov.jpg", "", ""])
        messagebox.showinfo("Шаблон сохранен", f"Заполните файл в Excel:\n{filepath}\n\nФотографии положите в ту же папку, где лежит таблица.")

def run_badge_batch_print():
    batch_file = filedialog.askopenfilename(title="Массовая печать: выберите CSV со списком сотрудников",
                                            filetypes=[("CSV", "*.csv"), ("Все файлы", "*.*")])
    if not batch_file:
        return
    folder = os.path.dirname(batch_file)
    items = []
    try:
        with open(batch_file, "r", encoding="utf-8-sig") as f:
            rows = list(csv.reader(f, delimiter=";"))
            if len(rows) > 1:
                for r in rows[1:]:
                    if len(r) >= 4 and r[1].strip():
                        photo_filename = r[7].strip() if len(r) > 7 else ""
                        photo_full_path = os.path.join(folder, photo_filename) if photo_filename else ""
                        if not os.path.exists(photo_full_path):
                            photo_full_path = ""
                        sur = r[1].strip(); nam = r[2].strip(); pat = r[3].strip() if len(r) > 3 else ""
                        issue_d = r[8].strip() if len(r) > 8 and r[8].strip() else (b_issue_ent.get().strip() or datetime.now().strftime("%d.%m.%Y"))
                        valid_d = r[9].strip() if len(r) > 9 and r[9].strip() else (b_valid_ent.get().strip() or add_years_safe(datetime.now(), 5).strftime("%d.%m.%Y"))
                        items.append({
                            "tab_num": r[0].strip(), "surname": sur, "name": nam, "patronymic": pat,
                            "fio": f"{sur} {nam} {pat}".strip(),
                            "role": r[4].strip() if len(r) > 4 else "Сотрудник",
                            "park": r[5].strip() if len(r) > 5 else badge_park_cb.get().strip(),
                            "phone": r[6].strip() if len(r) > 6 else "",
                            "photo_path": photo_full_path, "issue_date": issue_d, "valid_until": valid_d
                        })
    except Exception as e:
        messagebox.showerror("Ошибка чтения", f"Не удалось прочитать файл: {e}")
        return
    if not items:
        messagebox.showwarning("Пусто", "В файле нет записей.")
        return
    save_pdf_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
                                                 initialfile=f"Массовая_печать_бейджей_{len(items)}шт.pdf")
    if not save_pdf_path:
        return
    p_win = tk.Toplevel(root); p_win.title("Массовая печать бейджей"); p_win.geometry("420x130")
    p_win.transient(root); p_win.grab_set()
    lbl_p = ttk.Label(p_win, text="Подготовка бейджей...", font=F(10)); lbl_p.pack(pady=(15, 8))
    p_bar = ttk.Progressbar(p_win, length=340, mode="determinate"); p_bar.pack(pady=5)
    p_win.update()
    rendered_badges = []
    for idx, item in enumerate(items):
        rendered_badges.append(render_single_badge_image(item))
        p_bar["value"] = ((idx + 1) / len(items)) * 50
        lbl_p.config(text=f"Отрисовка {idx + 1} из {len(items)} бейджей...")
        p_win.update()
    pdf_pages = []
    cols, rows = 3, 3
    per_page = cols * rows
    total_pages = (len(rendered_badges) + per_page - 1) // per_page
    for page_i in range(total_pages):
        chunk = rendered_badges[page_i * per_page: (page_i + 1) * per_page]
        a4_sheet = Image.new("RGB", (2480, 3508), "#FFFFFF")
        draw_a4 = ImageDraw.Draw(a4_sheet)
        total_w = cols * CARD_W; total_h = rows * CARD_H
        start_x = (2480 - total_w) // 2; start_y = (3508 - total_h) // 2
        for i_card, b_img in enumerate(chunk):
            r = i_card // cols; c = i_card % cols
            x = start_x + c * CARD_W; y = start_y + r * CARD_H
            a4_sheet.paste(b_img, (x, y))
            draw_a4.rectangle([x, y, x + CARD_W, y + CARD_H], outline="#A0AEC0", width=2)
        draw_a4.text((1240, start_y - 60), "СПБ ГУП «ГОРЭЛЕКТРОТРАНС» — ЛИСТ ПЕЧАТИ ПРОПУСКОВ РАБОТНИКОВ (85 × 54 мм)",
                     fill="#718096", font=get_styled_font("light", 32), anchor="mm")
        draw_sheet_brand_icons(draw_a4, 150, start_y - 60, size=44)
        pdf_pages.append(a4_sheet)
        p_bar["value"] = 50 + ((page_i + 1) / total_pages) * 50
        lbl_p.config(text=f"Компоновка листа А4 №{page_i + 1} из {total_pages}...")
        p_win.update()
    pdf_pages[0].save(save_pdf_path, "PDF", resolution=300.0, save_all=True, append_images=pdf_pages[1:])
    for item in items:
        add_badge_to_log(item)
    p_win.destroy()
    if messagebox.askyesno("Успех", f"Массовая печать: {len(items)} бейджей на {len(pdf_pages)} л. А4!\n\nОткрыть PDF?"):
        try:
            os.startfile(save_pdf_path)
        except Exception:
            pass

def open_badge_batch_window():
    bwin = tk.Toplevel(root); bwin.title("Массовая печать постоянных бейджей")
    bwin.geometry("560x290"); bwin.transient(root); bwin.grab_set()
    f = ttk.Frame(bwin, padding="20"); f.pack(fill="both", expand=True)
    ttk.Label(f, text="МАССОВАЯ ПЕЧАТЬ бейджей работников из Excel / CSV", font=F(11, True)).pack(anchor="w", pady=(0, 10))
    ttk.Label(f, text="1. Скачайте шаблон и заполните сотрудников.\n"
                      "2. Укажите имена файлов фото (лежат рядом с CSV).\n"
                      "3. Выберите файл — бейджи разместятся на А4 (сетка 3×3).", justify="left").pack(anchor="w", pady=(0, 15))
    tk.Button(f, text="📥 1. Скачать пустой шаблон (CSV)", command=export_badge_batch_template,
              bg="#ECEFF1", font=F(10), pady=6, relief="groove", cursor="hand2").pack(fill="x", pady=4)
    tk.Button(f, text="🚀 2. Выбрать файл и напечатать массово", command=lambda: (bwin.destroy(), run_badge_batch_print()),
              bg="#0A2540", fg="white", font=F(10, True), pady=8, relief="flat", cursor="hand2").pack(fill="x", pady=6)

# ============================================================
# ЖУРНАЛ ТС
# ============================================================
def open_interactive_journal():
    records = read_log_records()
    win = tk.Toplevel(root); win.title("Журнал выданных пропусков ТС — ГЭТ СПб")
    win.geometry("1150x620"); win.minsize(900, 450); win.transient(root)
    f_filter = ttk.Frame(win, padding="10"); f_filter.pack(fill="x")
    ttk.Label(f_filter, text="🔍 Поиск:").pack(side="left", padx=(0, 5))
    search_var = tk.StringVar(); ttk.Entry(f_filter, textvariable=search_var, width=32).pack(side="left")
    filter_var = tk.StringVar(value="all")
    ttk.Radiobutton(f_filter, text="Все", variable=filter_var, value="all").pack(side="left", padx=10)
    ttk.Radiobutton(f_filter, text="Активные", variable=filter_var, value="active").pack(side="left", padx=5)
    ttk.Radiobutton(f_filter, text="Просроченные", variable=filter_var, value="expired").pack(side="left", padx=5)
    f_top = ttk.Frame(win, padding="10"); f_top.pack(fill="both", expand=True)
    columns = ("num", "plate", "zone", "driver", "phone", "issue", "valid")
    tree = ttk.Treeview(f_top, columns=columns, show="headings", selectmode="extended")
    for col, title, w, anc in [("num", "№ Пропуска", 95, "center"), ("plate", "Госномер", 110, "center"),
                               ("zone", "Зона", 150, "w"), ("driver", "Водитель", 260, "w"),
                               ("phone", "Телефон", 130, "center"), ("issue", "Выдан", 85, "center"), ("valid", "До", 85, "center")]:
        tree.heading(col, text=title); tree.column(col, width=w, anchor=anc)
    scroll = ttk.Scrollbar(f_top, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True); scroll.pack(side="right", fill="y")
    f_bottom = ttk.Frame(win, padding="10"); f_bottom.pack(fill="x")
    lbl_status = ttk.Label(f_bottom, text=f"Всего в журнале: {len(records)} шт.", font=F(9, True)); lbl_status.pack(side="left")

    def apply_filter(*args):
        query = search_var.get().lower(); status = filter_var.get(); today = datetime.now().date()
        tree.delete(*tree.get_children()); count = 0
        for idx, r in enumerate(records):
            if query and not any(query in str(cell).lower() for cell in r):
                continue
            if status != "all":
                valid_str = r[6] if len(r) > 6 else ""
                try:
                    is_active = datetime.strptime(valid_str.strip(), "%d.%m.%Y").date() >= today
                    if (status == "active" and not is_active) or (status == "expired" and is_active):
                        continue
                except Exception:
                    pass
            tree.insert("", "end", iid=str(idx), values=r); count += 1
        lbl_status.config(text=f"Найдено: {count} из {len(records)}")
    search_var.trace_add("write", apply_filter); filter_var.trace_add("write", apply_filter); apply_filter()

    def delete_selected():
        selected = tree.selection()
        if not selected:
            messagebox.showinfo("Выбор", "Выберите записи для удаления.", parent=win); return
        if not messagebox.askyesno("Подтверждение", f"Удалить выбранные записи ({len(selected)} шт.)?", parent=win):
            return
        sel_ids = set(int(i) for i in selected)
        curr = read_log_records()
        updated = [row for i, row in enumerate(curr) if i not in sel_ids]
        if safe_write_log_records(updated):
            records.clear(); records.extend(updated); apply_filter()

    def edit_selected():
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Выбор", "Выберите запись для редактирования.", parent=win); return
        idx = int(sel[0]); rec = list(records[idx])
        ewin = tk.Toplevel(win); ewin.title("Редактирование записи журнала ТС")
        ewin.geometry("560x420"); ewin.transient(win); ewin.grab_set()
        f_e = ttk.Frame(ewin, padding=20); f_e.pack(fill="both", expand=True)
        fields = ["Номер пропуска", "Гос. номер", "Зона допуска", "Водитель", "Телефон", "Дата выдачи", "Действителен до"]
        entries = []
        for i, lbl in enumerate(fields):
            ttk.Label(f_e, text=lbl, font=F(9, True)).grid(row=i, column=0, sticky="w", pady=4)
            e = ttk.Entry(f_e, width=42, font=F(10)); e.grid(row=i, column=1, pady=4, sticky="w")
            e.insert(0, rec[i] if i < len(rec) else ""); entries.append(e)
        def save_changes():
            records[idx] = [e.get().strip() for e in entries]
            if safe_write_log_records(records):
                apply_filter(); ewin.destroy()
        tk.Button(f_e, text="💾 Сохранить изменения", command=save_changes, bg="#2E7D32", fg="white",
                  font=F(10, True), pady=6, relief="flat", cursor="hand2").grid(row=len(fields) + 1, column=0, columnspan=2, pady=20)

    def open_excel():
        if not os.path.exists(LOG_XLSX_FILE):
            export_records_to_xlsx(read_log_records(), PASS_COLS_DEF, LOG_XLSX_FILE, "Журнал пропусков ТС")
        try:
            os.startfile(LOG_XLSX_FILE)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось открыть файл: {e}", parent=win)

    tk.Button(f_bottom, text="✏️ Изменить запись", command=edit_selected, bg="#1976D2", fg="white",
              font=F(9, True), relief="flat", padx=12, pady=6, cursor="hand2").pack(side="left", padx=(0, 6))
    tk.Button(f_bottom, text="📄 Открыть в Excel", command=open_excel, bg="#2E7D32", fg="white",
              font=F(9, True), relief="flat", padx=12, pady=6, cursor="hand2").pack(side="right")
    tk.Button(f_bottom, text="❌ Удалить выбранное", command=delete_selected, bg="#C62828", fg="white",
              font=F(9, True), relief="flat", padx=12, pady=6, cursor="hand2").pack(side="right", padx=(0, 6))

# ============================================================
# ЖУРНАЛ БЕЙДЖЕЙ
# ============================================================
def open_badge_journal():
    records = read_badge_log_records()
    win = tk.Toplevel(root); win.title("Журнал постоянных пропусков работников — ГЭТ СПб")
    win.geometry("1150x620"); win.minsize(900, 450); win.transient(root)
    f_filter = ttk.Frame(win, padding="10"); f_filter.pack(fill="x")
    ttk.Label(f_filter, text="🔍 Поиск:").pack(side="left", padx=(0, 5))
    search_var = tk.StringVar(); ttk.Entry(f_filter, textvariable=search_var, width=32).pack(side="left")
    filter_var = tk.StringVar(value="all")
    ttk.Radiobutton(f_filter, text="Все", variable=filter_var, value="all").pack(side="left", padx=10)
    ttk.Radiobutton(f_filter, text="Активные", variable=filter_var, value="active").pack(side="left", padx=5)
    ttk.Radiobutton(f_filter, text="Просроченные", variable=filter_var, value="expired").pack(side="left", padx=5)
    f_top = ttk.Frame(win, padding="10"); f_top.pack(fill="both", expand=True)
    columns = ("num", "fio", "role", "park", "phone", "issue", "valid")
    tree = ttk.Treeview(f_top, columns=columns, show="headings", selectmode="extended")
    for col, title, w, anc in [("num", "Табельный №", 105, "center"), ("fio", "ФИО сотрудника", 240, "w"),
                               ("role", "Должность", 180, "w"), ("park", "Подразделение", 200, "w"),
                               ("phone", "Телефон", 120, "center"), ("issue", "Выдан", 85, "center"), ("valid", "До", 85, "center")]:
        tree.heading(col, text=title); tree.column(col, width=w, anchor=anc)
    scroll = ttk.Scrollbar(f_top, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True); scroll.pack(side="right", fill="y")
    f_bottom = ttk.Frame(win, padding="10"); f_bottom.pack(fill="x")
    lbl_status = ttk.Label(f_bottom, text=f"Всего в журнале: {len(records)} шт.", font=F(9, True)); lbl_status.pack(side="left")

    def apply_filter(*args):
        query = search_var.get().lower(); status = filter_var.get(); today = datetime.now().date()
        tree.delete(*tree.get_children()); count = 0
        for idx, r in enumerate(records):
            if query and not any(query in str(cell).lower() for cell in r):
                continue
            if status != "all":
                valid_str = r[6] if len(r) > 6 else ""
                try:
                    is_active = datetime.strptime(valid_str.strip(), "%d.%m.%Y").date() >= today
                    if (status == "active" and not is_active) or (status == "expired" and is_active):
                        continue
                except Exception:
                    pass
            tree.insert("", "end", iid=str(idx), values=r); count += 1
        lbl_status.config(text=f"Найдено: {count} из {len(records)}")
    search_var.trace_add("write", apply_filter); filter_var.trace_add("write", apply_filter); apply_filter()

    def delete_selected():
        selected = tree.selection()
        if not selected:
            messagebox.showinfo("Выбор", "Выберите записи для удаления.", parent=win); return
        if not messagebox.askyesno("Подтверждение", f"Удалить выбранные бейджи ({len(selected)} шт.)?", parent=win):
            return
        sel_ids = set(int(i) for i in selected)
        curr = read_badge_log_records()
        updated = [row for i, row in enumerate(curr) if i not in sel_ids]
        if safe_write_badge_log_records(updated):
            records.clear(); records.extend(updated); apply_filter()

    def edit_selected():
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Выбор", "Выберите запись для редактирования.", parent=win); return
        idx = int(sel[0]); rec = list(records[idx])
        ewin = tk.Toplevel(win); ewin.title("Редактирование записи журнала работников")
        ewin.geometry("560x420"); ewin.transient(win); ewin.grab_set()
        f_e = ttk.Frame(ewin, padding=20); f_e.pack(fill="both", expand=True)
        fields = ["Табельный номер", "ФИО сотрудника", "Должность", "Подразделение", "Телефон", "Дата выдачи", "Действителен до"]
        entries = []
        for i, lbl in enumerate(fields):
            ttk.Label(f_e, text=lbl, font=F(9, True)).grid(row=i, column=0, sticky="w", pady=4)
            e = ttk.Entry(f_e, width=42, font=F(10)); e.grid(row=i, column=1, pady=4, sticky="w")
            e.insert(0, rec[i] if i < len(rec) else ""); entries.append(e)
        def save_changes():
            records[idx] = [e.get().strip() for e in entries]
            if safe_write_badge_log_records(records):
                apply_filter(); ewin.destroy()
        tk.Button(f_e, text="💾 Сохранить изменения", command=save_changes, bg="#2E7D32", fg="white",
                  font=F(10, True), pady=6, relief="flat", cursor="hand2").grid(row=len(fields) + 1, column=0, columnspan=2, pady=20)

    def open_excel():
        if not os.path.exists(BADGE_LOG_XLSX):
            export_records_to_xlsx(read_badge_log_records(), BADGE_COLS_DEF, BADGE_LOG_XLSX, "Журнал постоянных бейджей")
        try:
            os.startfile(BADGE_LOG_XLSX)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось открыть файл: {e}", parent=win)

    tk.Button(f_bottom, text="✏️ Изменить запись", command=edit_selected, bg="#1976D2", fg="white",
              font=F(9, True), relief="flat", padx=12, pady=6, cursor="hand2").pack(side="left", padx=(0, 6))
    tk.Button(f_bottom, text="📄 Открыть в Excel", command=open_excel, bg="#2E7D32", fg="white",
              font=F(9, True), relief="flat", padx=12, pady=6, cursor="hand2").pack(side="right")
    tk.Button(f_bottom, text="❌ Удалить выбранное", command=delete_selected, bg="#C62828", fg="white",
              font=F(9, True), relief="flat", padx=12, pady=6, cursor="hand2").pack(side="right", padx=(0, 6))

# ============================================================
# ГЕНЕРАЦИЯ И ПЕЧАТЬ ПРОПУСКОВ ТС
# ============================================================
def build_single_or_double_doc():
    d_issue = validate_date_string(entry_issue.get(), "Дата выдачи") or datetime.now()
    d_valid = validate_date_string(entry_valid.get(), "Действителен до")
    if not d_valid:
        messagebox.showwarning("Укажите срок", "Заполните поле «Действителен до» (ДД.ММ.ГГГГ).")
        return None, None, None
    if is_temp_car_var.get():
        max_allowed = add_months_safe(d_issue, 3)
        if d_valid > max_allowed:
            messagebox.showwarning("Превышен срок", f"Временный пропуск выдается не более чем на 3 месяца!\n\nМаксимальная дата: {max_allowed.strftime('%d.%m.%Y')}")
            return None, None, None
    d1_pos = p1_d_pos.get().strip(); d1_fio = p1_d_fio.get().strip()
    p1 = {"num": p1_num.get().strip() or "б/н", "plate": p1_plate_var.get().strip(),
          "brand": p1_brand.get().strip(), "model": p1_model.get().strip(),
          "type": p1_type.get().strip(), "color": p1_color.get().strip(),
          "d_pos": d1_pos, "d_fio": d1_fio, "phone": p1_d_phone.get().strip(),
          "driver_full": f"{d1_pos} {d1_fio}".strip(), "territory": p1_territory.get().strip()}
    common = {"issue_date": d_issue.strftime("%d.%m.%Y"), "valid_until": d_valid.strftime("%d.%m.%Y"),
              "otb_post": entry_otb_post.get().strip(), "otb_name": entry_otb_name.get().strip(),
              "is_temporary": is_temp_car_var.get()}
    if not p1["plate"]:
        messagebox.showwarning("Внимание", "Заполните «Гос. номер автомобиля» во вкладке «Пропуск №1»!")
        main_notebook.select(0); auto_notebook.select(0); p1_plate_entry.focus()
        return None, None, None
    mode = print_mode_var.get()
    img1 = render_pass(p1, common)
    passes_to_log = []
    final_doc = None; file_prefix = ""; next_num = increment_number(p1["num"])
    img2 = img1
    if mode == "a4":
        d2_pos = p2_d_pos.get().strip(); d2_fio = p2_d_fio.get().strip()
        p2 = {"num": p2_num.get().strip() or "б/н", "plate": p2_plate_var.get().strip(),
              "brand": p2_brand.get().strip(), "model": p2_model.get().strip(),
              "type": p2_type.get().strip(), "color": p2_color.get().strip(),
              "d_pos": d2_pos, "d_fio": d2_fio, "phone": p2_d_phone.get().strip(),
              "driver_full": f"{d2_pos} {d2_fio}".strip(), "territory": p2_territory.get().strip()}
        if not p2["plate"]:
            if messagebox.askyesno("Второй пропуск не заполнен",
                                   "Выбран лист А4, но во вкладке «Пропуск №2» нет номера.\n\n"
                                   "• «Да» — напечатать 2 копии Пропуска №1.\n"
                                   "• «Нет» — напечатать 1 пропуск (А5)."):
                img2 = img1
                file_prefix = f"Пропуск_{p1['num']}_2копии_А4"
                next_num = increment_number(p1["num"])
                passes_to_log.append(dict(p1, **common))
            else:
                mode = "a5"
                final_doc = img1
                file_prefix = f"Пропуск_{p1['num']}_А5"
                next_num = increment_number(p1["num"])
                passes_to_log.append(dict(p1, **common))
        else:
            img2 = render_pass(p2, common)
            file_prefix = f"Пропуска_{p1['num']}_{p2['num']}"
            next_num = increment_number(p2["num"])
            passes_to_log.append(dict(p1, **common)); passes_to_log.append(dict(p2, **common))
    if mode == "a4":
        final_doc = Image.new("RGB", (2480, 3508), "white")
        draw = ImageDraw.Draw(final_doc)
        y_slot = 3508 // 2
        final_doc.paste(img1, (0, (y_slot - img1.height) // 2))
        final_doc.paste(img2, (0, y_slot + (y_slot - img2.height) // 2))
        for x in range(120, 2360, 45):
            draw.line([(x, y_slot), (x + 25, y_slot)], fill="#9E9E9E", width=3)
        draw.text((1240, y_slot), "   ✂   ЛИНИЯ РАЗРЕЗА   ✂   ", fill="#757575", font=get_styled_font("geo", 36), anchor="mm")
    elif mode == "a5":
        final_doc = img1
        file_prefix = f"Пропуск_{p1['num']}_А5"
        if not passes_to_log:
            passes_to_log.append(dict(p1, **common))
    return final_doc, file_prefix, (passes_to_log, next_num)

def generate_pass():
    final_doc, file_prefix, meta = build_single_or_double_doc()
    if not final_doc:
        return
    passes_to_log, next_num = meta
    filepath = filedialog.asksaveasfilename(defaultextension=".pdf",
                                            filetypes=[("PDF Документ (для печати)", "*.pdf"), ("Изображение JPEG", "*.jpg")],
                                            initialfile=f"{file_prefix}.pdf")
    if filepath:
        final_doc.save(filepath, resolution=300.0)
        add_passes_to_log(passes_to_log)
        p1_num.delete(0, tk.END); p1_num.insert(0, next_num)
        p2_num.delete(0, tk.END); p2_num.insert(0, increment_number(next_num))
        save_settings(); clear_auto_forms()
        messagebox.showinfo("Готово", f"Документ сформирован!\nСледующий номер: {next_num}")

def get_available_printers():
    try:
        ps_cmd = "Add-Type -AssemblyName System.Drawing; [System.Drawing.Printing.PrinterSettings]::InstalledPrinters"
        flags = 0x08000000 if sys.platform == "win32" else 0
        res = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                             creationflags=flags, capture_output=True, text=True, timeout=10)
        if res.returncode == 0:
            return ["По умолчанию"] + [p.strip() for p in res.stdout.split('\n') if p.strip()]
    except Exception:
        pass
    return ["По умолчанию"]

def send_image_to_windows_printer(pil_image, printer_name=None):
    temp_img = os.path.join(SCRIPT_DIR, "_temp_print_job.png")
    try:
        pil_image.save(temp_img, "PNG")
        is_landscape = "$true" if pil_image.width > pil_image.height else "$false"
        escaped_path = temp_img.replace("'", "''")
        printer_cmd = ""
        if printer_name and printer_name != "По умолчанию":
            printer_cmd = f"$doc.PrinterSettings.PrinterName = '{printer_name.replace(chr(39), chr(39)*2)}'; "
        ps_cmd = (
            f"Add-Type -AssemblyName System.Drawing; "
            f"$doc = New-Object System.Drawing.Printing.PrintDocument; "
            f"{printer_cmd}"
            f"$doc.DefaultPageSettings.Landscape = {is_landscape}; "
            f"$doc.OriginAtMargins = $false; "
            f"$img = [System.Drawing.Image]::FromFile('{escaped_path}'); "
            f"$doc.add_PrintPage({{ "
            f"  param($s, $e) "
            f"  $e.Graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic; "
            f"  $pb = $e.MarginBounds; "
            f"  $ratio = $img.Width / $img.Height; "
            f"  if ($pb.Width / $pb.Height -gt $ratio) {{ "
            f"    $w = $pb.Height * $ratio; $h = $pb.Height; "
            f"    $x = $pb.X + ($pb.Width - $w) / 2; $y = $pb.Y; "
            f"  }} else {{ "
            f"    $w = $pb.Width; $h = $pb.Width / $ratio; "
            f"    $x = $pb.X; $y = $pb.Y + ($pb.Height - $h) / 2; "
            f"  }} "
            f"  $destRect = New-Object System.Drawing.RectangleF($x, $y, $w, $h); "
            f"  $e.Graphics.DrawImage($img, $destRect); "
            f"}}); "
            f"$doc.Print(); "
            f"$img.Dispose()"
        )
        flags = 0x08000000 if sys.platform == "win32" else 0
        res = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                             creationflags=flags, capture_output=True, text=True, timeout=20)
        return res.returncode == 0
    except Exception:
        return False

def direct_print_pass():
    final_doc, file_prefix, meta = build_single_or_double_doc()
    if not final_doc:
        return
    passes_to_log, next_num = meta
    add_passes_to_log(passes_to_log)
    p1_num.delete(0, tk.END); p1_num.insert(0, next_num)
    p2_num.delete(0, tk.END); p2_num.insert(0, increment_number(next_num))
    save_settings(); clear_auto_forms()
    if send_image_to_windows_printer(final_doc, printer_var.get()):
        messagebox.showinfo("Печать", "Документ успешно отправлен на принтер!")
    else:
        temp_pdf = os.path.join(SCRIPT_DIR, f"_temp_print_{file_prefix}.pdf")
        final_doc.save(temp_pdf, resolution=300.0)
        try:
            os.startfile(temp_pdf)
        except Exception:
            pass
        messagebox.showinfo("Печать", "Документ открыт для печати. Нажмите Ctrl+P.")

# ============================================================
# КАДРИРОВАНИЕ ФОТО (зум + сдвиг + СОХРАНЕНИЕ)
# ============================================================
selected_badge_photo_path = None

def compute_crop_from_state(im, orig_w, orig_h, state, frame_box, canvas_size):
    CANVAS_W, CANVAS_H = canvas_size
    frame_x, frame_y, frame_w, frame_h = frame_box
    cur_scale = state["base_scale"] * state["scale"]
    scaled_w = orig_w * cur_scale; scaled_h = orig_h * cur_scale
    img_left = (CANVAS_W / 2 + state["offset_x"]) - scaled_w / 2
    img_top = (CANVAS_H / 2 + state["offset_y"]) - scaled_h / 2
    rx = int((frame_x - img_left) / cur_scale); ry = int((frame_y - img_top) / cur_scale)
    rw = int(frame_w / cur_scale); rh = int(frame_h / cur_scale)
    rx = max(0, min(rx, orig_w - rw)); ry = max(0, min(ry, orig_h - rh))
    rw = min(rw, orig_w - rx); rh = min(rh, orig_h - ry)
    return im.crop((rx, ry, rx + rw, ry + rh)), (rx, ry, rw, rh)

def open_crop_window(image_path):
    crop_win = tk.Toplevel(root)
    crop_win.title("Кадрирование фотографии — колесо мыши: масштаб, ЛКМ: перемещение")
    crop_win.geometry("760x920"); crop_win.minsize(620, 700)
    crop_win.transient(root); crop_win.grab_set()
    crop_win.configure(bg="#22303C")
    try:
        im = Image.open(image_path).convert("RGB")
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось открыть фото:\n{e}", parent=crop_win)
        crop_win.destroy(); return
    orig_w, orig_h = im.size
    CANVAS_W, CANVAS_H = 700, 700
    frame_h = int(CANVAS_H * 0.88); frame_w = int(frame_h * (3 / 4))
    frame_x = (CANVAS_W - frame_w) // 2; frame_y = (CANVAS_H - frame_h) // 2
    frame_box = (frame_x, frame_y, frame_w, frame_h)
    base_scale = max(frame_w / orig_w, frame_h / orig_h)
    state = {"scale": 1.0, "offset_x": 0, "offset_y": 0, "is_dragging": False,
             "last_x": 0, "last_y": 0, "photo_tk": None, "base_scale": base_scale}

    btn_bar = tk.Frame(crop_win, bg="#22303C"); btn_bar.pack(side="bottom", fill="x", padx=16, pady=(6, 14))
    zoom_bar = tk.Frame(crop_win, bg="#22303C"); zoom_bar.pack(side="bottom", fill="x", padx=16, pady=4)
    tk.Label(crop_win, text="🖱 Колесо мыши — масштаб   •   Зажмите ЛКМ и тяните — перемещение   •   Лицо должно быть в красной рамке",
             bg="#22303C", fg="#E8EEF4", font=F(10)).pack(side="bottom", fill="x", pady=(8, 4))
    c = tk.Canvas(crop_win, width=CANVAS_W, height=CANVAS_H, bg="#141A20", highlightthickness=0)
    c.pack(side="top", fill="both", expand=True, padx=10, pady=(10, 0))

    zoom_lbl = tk.Label(crop_win, text="Масштаб: 100%", bg="#22303C", fg="#FFD54F", font=F(10, True), width=16)

    def redraw():
        c.delete("photo")
        cur_scale = state["base_scale"] * state["scale"]
        sw = max(1, int(orig_w * cur_scale)); sh = max(1, int(orig_h * cur_scale))
        try:
            disp_im = im.resize((sw, sh), Image.Resampling.LANCZOS)
            state["photo_tk"] = ImageTk.PhotoImage(disp_im)
            draw_x = CANVAS_W / 2 + state["offset_x"] - sw / 2
            draw_y = CANVAS_H / 2 + state["offset_y"] - sh / 2
            c.create_image(draw_x, draw_y, image=state["photo_tk"], anchor="nw", tags="photo")
            c.tag_lower("photo")
        except Exception:
            pass
        zoom_lbl.config(text=f"Масштаб: {int(state['scale'] * 100)}%")

    def zoom(factor):
        state["scale"] = max(0.25, min(state["scale"] * factor, 6.0))
        redraw()

    def on_wheel(event):
        zoom(1.12 if event.delta > 0 else 0.89)
        return "break"
    def on_press(event):
        state["is_dragging"] = True; state["last_x"] = event.x; state["last_y"] = event.y
    def on_drag(event):
        if state["is_dragging"]:
            state["offset_x"] += event.x - state["last_x"]; state["offset_y"] += event.y - state["last_y"]
            state["last_x"] = event.x; state["last_y"] = event.y
            redraw()
    def on_release(event):
        state["is_dragging"] = False

    c.bind("<MouseWheel>", on_wheel)
    c.bind("<Button-4>", lambda e: zoom(1.12))
    c.bind("<Button-5>", lambda e: zoom(0.89))
    c.bind("<ButtonPress-1>", on_press)
    c.bind("<B1-Motion>", on_drag)
    c.bind("<ButtonRelease-1>", on_release)

    def draw_frame_overlay():
        c.delete("frame")
        fx, fy, fw, fh = frame_box
        c.create_rectangle(0, 0, CANVAS_W, fy, fill="#0B1116", stipple="gray50", outline="", tags="frame")
        c.create_rectangle(0, fy + fh, CANVAS_W, CANVAS_H, fill="#0B1116", stipple="gray50", outline="", tags="frame")
        c.create_rectangle(0, fy, fx, fy + fh, fill="#0B1116", stipple="gray50", outline="", tags="frame")
        c.create_rectangle(fx + fw, fy, CANVAS_W, fy + fh, fill="#0B1116", stipple="gray50", outline="", tags="frame")
        c.create_rectangle(fx, fy, fx + fw, fy + fh, outline="#E53935", width=4, tags="frame")
        c.create_line(fx + fw / 3, fy, fx + fw / 3, fy + fh, fill="#FFFFFF", width=1, tags="frame")
        c.create_line(fx + 2 * fw / 3, fy, fx + 2 * fw / 3, fy + fh, fill="#FFFFFF", width=1, tags="frame")
        c.create_line(fx, fy + fh / 3, fx + fw, fy + fh / 3, fill="#FFFFFF", width=1, tags="frame")
        c.create_line(fx, fy + 2 * fh / 3, fx + fw, fy + 2 * fh / 3, fill="#FFFFFF", width=1, tags="frame")
        c.create_text(CANVAS_W // 2, max(14, fy - 18), text="ОБЛАСТЬ ФОТО НА БЕЙДЖЕ (3:4)",
                      fill="#FF8A80", font=F(10, True), tags="frame")

    redraw(); draw_frame_overlay()

    tk.Button(zoom_bar, text="➖  Уменьшить", command=lambda: zoom(0.85), bg="#C0392B", fg="white",
              font=F(10, True), padx=12, pady=5, relief="flat", cursor="hand2").pack(side="left", padx=3)
    tk.Button(zoom_bar, text="↺  Сброс", command=lambda: (state.update({"scale": 1.0, "offset_x": 0, "offset_y": 0}), redraw()),
              bg="#546E7A", fg="white", font=F(10, True), padx=12, pady=5, relief="flat", cursor="hand2").pack(side="left", padx=3)
    tk.Button(zoom_bar, text="➕  Увеличить", command=lambda: zoom(1.15), bg="#27AE60", fg="white",
              font=F(10, True), padx=12, pady=5, relief="flat", cursor="hand2").pack(side="left", padx=3)
    zoom_lbl.pack(side="left", padx=10)

    def save_and_apply():
        cropped, box = compute_crop_from_state(im, orig_w, orig_h, state, frame_box, (CANVAS_W, CANVAS_H))
        temp_path = os.path.join(SCRIPT_DIR, "_temp_cropped_photo.jpg")
        try:
            cropped.save(temp_path, "JPEG", quality=95)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить кадр:\n{e}", parent=crop_win); return
        global selected_badge_photo_path
        selected_badge_photo_path = temp_path
        lbl_photo_status.config(text=f"✓ Фото: {box[2]}×{box[3]} px (обрезано вручную)", fg="#2E7D32")
        crop_win.destroy()
        update_badge_preview()

    def save_as_file():
        cropped, box = compute_crop_from_state(im, orig_w, orig_h, state, frame_box, (CANVAS_W, CANVAS_H))
        path = filedialog.asksaveasfilename(parent=crop_win, defaultextension=".jpg",
                                            filetypes=[("JPEG", "*.jpg"), ("PNG", "*.png")],
                                            initialfile="foto_sotrudnika_3x4.jpg")
        if not path:
            return
        try:
            if path.lower().endswith(".png"):
                cropped.save(path)
            else:
                cropped.save(path, "JPEG", quality=95)
            messagebox.showinfo("Сохранено", f"Фотография сохранена:\n{path}\n\nРазмер кадра: {box[2]}×{box[3]} px", parent=crop_win)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить файл:\n{e}", parent=crop_win)

    tk.Button(btn_bar, text="💾  СОХРАНИТЬ И ПРИМЕНИТЬ", command=save_and_apply, bg="#27AE60", fg="white",
              font=F(12, True), pady=11, relief="flat", cursor="hand2").pack(side="left", fill="x", expand=True, padx=(0, 6))
    tk.Button(btn_bar, text="📁  Сохранить как файл...", command=save_as_file, bg="#1565C0", fg="white",
              font=F(11, True), pady=11, padx=14, relief="flat", cursor="hand2").pack(side="left", padx=(0, 6))
    tk.Button(btn_bar, text="❌  Отмена", command=crop_win.destroy, bg="#455A64", fg="white",
              font=F(11), pady=11, padx=14, relief="flat", cursor="hand2").pack(side="right")

# ============================================================
# БЕЙДЖ: ФОРМА И ПРЕДПРОСМОТР
# ============================================================
_badge_preview_job = None

def get_current_badge_dict_for_preview():
    sur = b_sur_var.get().strip() or "ФАМИЛИЯ"
    nam = b_nam_var.get().strip() or "ИМЯ"
    pat = b_pat_var.get().strip() or "ОТЧЕСТВО"
    return {"tab_num": b_tab_num_ent.get().strip() or "00000",
            "park": badge_park_cb.get().strip() or "ОСП «Трамвайный парк № 8»",
            "role": b_role_ent.get().strip() or "Должность",
            "surname": sur, "name": nam, "patronymic": pat,
            "fio": f"{sur} {nam} {pat}".strip(),
            "phone": b_phone_ent.get().strip(),
            "issue_date": b_issue_ent.get().strip() or datetime.now().strftime("%d.%m.%Y"),
            "valid_until": b_valid_ent.get().strip() or add_years_safe(datetime.now(), 5).strftime("%d.%m.%Y"),
            "photo_path": selected_badge_photo_path}

def update_badge_preview(*args, delay=60):
    global _badge_preview_job
    try:
        if _badge_preview_job is not None:
            root.after_cancel(_badge_preview_job)
        _badge_preview_job = root.after(delay, _do_badge_preview)
    except Exception:
        _do_badge_preview()

def _do_badge_preview():
    global _badge_preview_job
    _badge_preview_job = None
    try:
        badge_full = render_single_badge_image(get_current_badge_dict_for_preview(), silent=True)
        panel_w = b_right_preview_panel.winfo_width(); panel_h = b_right_preview_panel.winfo_height()
        if panel_w < 80: panel_w = 420
        if panel_h < 120: panel_h = 620
        max_w = max(120, panel_w - 40); max_h = max(160, panel_h - 130)
        ratio = CARD_H / CARD_W
        w = min(max_w, 1200); h = int(w * ratio)
        if h > max_h:
            h = max_h; w = int(h / ratio)
        thumb = badge_full.resize((max(60, w), max(80, h)), Image.Resampling.LANCZOS)
        photo_tk = ImageTk.PhotoImage(thumb)
        lbl_badge_live_preview.config(image=photo_tk, text="")
        lbl_badge_live_preview.image = photo_tk
    except Exception:
        pass

def select_badge_photo():
    path = filedialog.askopenfilename(title="Выберите фотографию сотрудника",
                                      filetypes=[("Файлы изображений", "*.png;*.jpg;*.jpeg;*.webp;*.bmp"), ("Все файлы", "*.*")])
    if path:
        lbl_photo_status.config(text="⏳ Открыт редактор кадрирования...", fg="#1565C0")
        open_crop_window(path)

def validate_and_get_badge_data():
    if not selected_badge_photo_path or not os.path.exists(selected_badge_photo_path):
        messagebox.showwarning("Фото обязательно", "Пожалуйста, выберите фотографию сотрудника и обрежьте её в редакторе!")
        return None
    d_issue = validate_date_string(b_issue_ent.get(), "Дата выдачи")
    if not d_issue:
        return None
    d_valid = validate_date_string(b_valid_ent.get(), "Действителен до")
    if not d_valid:
        return None
    if d_valid < d_issue:
        messagebox.showwarning("Ошибка дат", "Дата окончания не может быть раньше даты выдачи!")
        return None
    sur = b_sur_var.get().strip(); nam = b_nam_var.get().strip(); pat = b_pat_var.get().strip()
    if not (sur and nam):
        messagebox.showwarning("Заполните ФИО", "Заполните Фамилию и Имя сотрудника!")
        b_sur_ent.focus(); return None
    return {"tab_num": b_tab_num_ent.get().strip() or "00001",
            "park": badge_park_cb.get().strip(),
            "role": b_role_ent.get().strip() or "Сотрудник",
            "surname": sur, "name": nam, "patronymic": pat,
            "fio": f"{sur} {nam} {pat}".strip(),
            "phone": b_phone_ent.get().strip(),
            "issue_date": d_issue.strftime("%d.%m.%Y"),
            "valid_until": d_valid.strftime("%d.%m.%Y"),
            "photo_path": selected_badge_photo_path}

def get_badge_final_doc_and_prefix(b_data):
    badge_img = render_single_badge_image(b_data)
    mode = badge_print_mode_var.get()
    if mode == "card":
        return badge_img, f"Пропуск_{b_data['tab_num']}_{b_data['surname']}_CR80"
    if mode == "a4_grid":
        return build_a4_sheet_of_badges(badge_img, count=9), f"Пропуска_{b_data['tab_num']}_9шт_А4"
    final_doc = Image.new("RGB", (2480, 3508), "#FFFFFF")
    x_c = (2480 - CARD_W) // 2; y_c = (3508 - CARD_H) // 2
    final_doc.paste(badge_img, (x_c, y_c))
    ImageDraw.Draw(final_doc).rectangle([x_c, y_c, x_c + CARD_W, y_c + CARD_H], outline="#CBD2D9", width=2)
    return final_doc, f"Пропуск_{b_data['tab_num']}_1шт_А4"

def generate_badge_pdf():
    b_data = validate_and_get_badge_data()
    if not b_data:
        return
    final_doc, prefix = get_badge_final_doc_and_prefix(b_data)
    filepath = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Документ", "*.pdf")],
                                            initialfile=f"{prefix}.pdf")
    if filepath:
        final_doc.save(filepath, resolution=300.0)
        add_badge_to_log(b_data)
        next_num = increment_number(b_data["tab_num"])
        b_tab_num_ent.delete(0, tk.END); b_tab_num_ent.insert(0, next_num)
        save_settings(); clear_badge_form()
        messagebox.showinfo("Готово", f"Пропуск работника сформирован в PDF!\nСледующий табельный номер: {next_num}")

def direct_print_badge():
    b_data = validate_and_get_badge_data()
    if not b_data:
        return
    final_doc, prefix = get_badge_final_doc_and_prefix(b_data)
    add_badge_to_log(b_data)
    next_num = increment_number(b_data["tab_num"])
    b_tab_num_ent.delete(0, tk.END); b_tab_num_ent.insert(0, next_num)
    save_settings(); clear_badge_form()
    if send_image_to_windows_printer(final_doc, printer_var.get()):
        messagebox.showinfo("Печать", "Бейдж успешно отправлен на принтер!")
    else:
        temp_pdf = os.path.join(SCRIPT_DIR, f"_temp_badge_{b_data['tab_num']}.pdf")
        final_doc.save(temp_pdf, resolution=300.0)
        try:
            os.startfile(temp_pdf)
        except Exception:
            pass
        messagebox.showinfo("Печать", "Документ открыт для печати. Нажмите Ctrl+P.")

# ============================================================
# БЭКАП / ВОССТАНОВЛЕНИЕ
# ============================================================
def backup_database():
    filepath = filedialog.asksaveasfilename(defaultextension=".zip", filetypes=[("ZIP Архив", "*.zip")],
                                            initialfile=f"Backup_GET_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip")
    if not filepath:
        return
    try:
        with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
            for f in [CONFIG_FILE, LOG_CSV_FILE, BADGE_LOG_CSV, CARS_CACHE_FILE]:
                if os.path.exists(f):
                    zf.write(f, os.path.basename(f))
        messagebox.showinfo("Успех", "Резервная копия создана!")
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось создать бэкап: {e}")

def restore_database():
    filepath = filedialog.askopenfilename(title="Выберите ZIP-архив", filetypes=[("ZIP Архив", "*.zip")])
    if not filepath:
        return
    if not messagebox.askyesno("Внимание", "Текущие данные будут перезаписаны данными из архива. Продолжить?"):
        return
    try:
        with zipfile.ZipFile(filepath, 'r') as zf:
            zf.extractall(SCRIPT_DIR)
        messagebox.showinfo("Успех", "Данные восстановлены! Перезапустите программу.")
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось восстановить: {e}")

# ============================================================
# ГЛАВНОЕ ОКНО
# ============================================================
setup_ui_font()
find_echoes_font()
settings = load_settings()

root = tk.Tk()
root.title("СПб ГУП «Горэлектротранс» — Система выпуска пропусков и бейджей")
root.geometry("1500x920")
root.minsize(1080, 720)
root.configure(bg="#EEF2F6")
if os.path.exists(ICON_FILE):
    try:
        root.iconbitmap(ICON_FILE)
    except Exception:
        pass

def on_closing():
    if messagebox.askokcancel("Выход", "Закрыть программу?\n\nНезавершённые формы не будут сохранены."):
        root.destroy()
root.protocol("WM_DELETE_WINDOW", on_closing)

def clear_auto_forms():
    p1_plate_var.set(""); p2_plate_var.set("")
    for e in [p1_brand, p1_type, p1_model, p1_color, p1_d_pos, p1_d_fio, p1_d_phone,
              p2_brand, p2_type, p2_model, p2_color, p2_d_pos, p2_d_fio, p2_d_phone]:
        e.delete(0, tk.END)
    p1_territory.set(settings.get("territory", ""))
    p2_territory.set(settings.get("territory", ""))
    schedule_auto_preview()

def clear_badge_form():
    global selected_badge_photo_path
    selected_badge_photo_path = None
    for var in [b_sur_var, b_nam_var, b_pat_var]:
        var.set("")
    b_role_ent.delete(0, tk.END); b_phone_ent.delete(0, tk.END)
    today_now = datetime.now()
    b_issue_ent.delete(0, tk.END); b_issue_ent.insert(0, today_now.strftime("%d.%m.%Y"))
    b_valid_ent.delete(0, tk.END); b_valid_ent.insert(0, add_years_safe(today_now, 5).strftime("%d.%m.%Y"))
    lbl_photo_status.config(text="Фото не выбрано", fg="#C62828")
    update_badge_preview()

def clear_current_form():
    if main_notebook.index(main_notebook.select()) == 0:
        if messagebox.askyesno("Очистить форму", "Очистить поля пропусков на ТС (№1 и №2)?"):
            clear_auto_forms(); p1_plate_entry.focus()
    else:
        if messagebox.askyesno("Очистить форму", "Очистить данные сотрудника и выбранное фото?"):
            clear_badge_form()

style = ttk.Style(); style.theme_use("clam")
CLR_NAVY = "#0A2540"; CLR_TEAL = "#009FA0"; CLR_RED = "#D6204B"; CLR_BG = "#EEF2F6"; CLR_CARD = "#FFFFFF"
style.configure(".", background=CLR_BG, font=F(9))
style.configure("TLabel", background=CLR_BG, foreground="#2C3E50")
style.configure("TLabelframe", background=CLR_BG, borderwidth=0)
style.configure("TLabelframe.Label", background=CLR_BG, foreground=CLR_NAVY)
style.configure("TNotebook", background=CLR_BG, borderwidth=0)
style.configure("TNotebook.Tab", font=F(10, True), padding=[20, 9], background="#D0DCE5", foreground="#334E68")
style.map("TNotebook.Tab", background=[("selected", CLR_NAVY), ("active", "#BCCCDC")],
          foreground=[("selected", "#FFFFFF"), ("active", "#102A43")])
style.configure("Treeview", font=F(10), rowheight=26)
style.configure("Treeview.Heading", font=F(9, True))

header_frame = tk.Frame(root, bg=CLR_NAVY, height=78); header_frame.pack(fill="x")
strip_frame = tk.Frame(header_frame, height=5); strip_frame.pack(fill="x", side="top")
for clr in ("#1E2548", CLR_TEAL, CLR_RED):
    tk.Frame(strip_frame, bg=clr, height=5).pack(side="left", fill="both", expand=True)
tk.Label(header_frame, text="СПБ ГУП «ГОРЭЛЕКТРОТРАНС»", font=F(14, True), bg=CLR_NAVY, fg="#FFFFFF").pack(anchor="w", padx=20, pady=(9, 0))
_font_note = f"  •  брендбук-шрифт: {UI_FAMILY}" if UI_FAMILY != "Segoe UI" else ""
tk.Label(header_frame, text=f"Комплекс оформления пропусков на транспорт и постоянных пропусков работников{_font_note}",
         font=F(9), bg=CLR_NAVY, fg="#A0C4E2").pack(anchor="w", padx=20, pady=(0, 9))

sys_frame = tk.Frame(root, bg=CLR_BG); sys_frame.pack(fill="x", padx=12, pady=6)
tk.Label(sys_frame, text="🖨️ Принтер:", bg=CLR_BG, font=F(9, True)).pack(side="left")
printer_var = tk.StringVar(value=settings.get("last_printer", "По умолчанию"))
printer_cb = ttk.Combobox(sys_frame, textvariable=printer_var, state="readonly", width=38, font=F(9))
printer_cb.pack(side="left", padx=6)
printer_cb["values"] = get_available_printers()
if printer_var.get() not in printer_cb["values"]:
    printer_var.set("По умолчанию")
printer_cb.bind("<<ComboboxSelected>>", lambda e: save_settings())

tk.Button(sys_frame, text="🧹 ОЧИСТИТЬ ФОРМУ", command=clear_current_form, bg="#E91E63", fg="white",
          font=F(10, True), relief="flat", padx=14, pady=3, cursor="hand2").pack(side="right", padx=(6, 0))
tk.Button(sys_frame, text="♻️ Восстановить", command=restore_database, bg="#FF9800", fg="white",
          font=F(9, True), relief="flat", padx=10, pady=3, cursor="hand2").pack(side="right", padx=3)
tk.Button(sys_frame, text="💾 Бэкап", command=backup_database, bg="#4CAF50", fg="white",
          font=F(9, True), relief="flat", padx=10, pady=3, cursor="hand2").pack(side="right", padx=3)
tk.Button(sys_frame, text="🧪 Тест иконок", command=render_dot_icons_test_sheet, bg="#7E57C2", fg="white",
          font=F(9, True), relief="flat", padx=10, pady=3, cursor="hand2").pack(side="right", padx=3)

main_frame = ttk.Frame(root, padding="10"); main_frame.pack(fill="both", expand=True)
main_notebook = ttk.Notebook(main_frame); main_notebook.pack(fill="both", expand=True)

def _global_mousewheel(event):
    try:
        widget = root.winfo_containing(event.x_root, event.y_root)
    except Exception:
        return None
    steps = int(-1 * (event.delta / 120))
    while widget is not None:
        if isinstance(widget, tk.Canvas):
            try:
                widget.yview_scroll(steps, "units")
                return "break"
            except Exception:
                return None
        widget = getattr(widget, "master", None)
    return None
root.bind_all("<MouseWheel>", _global_mousewheel)

def make_scrollable(parent, bg_color):
    wrapper = tk.Frame(parent, bg=bg_color)
    canvas = tk.Canvas(wrapper, bg=bg_color, highlightthickness=0, bd=0)
    scroll = ttk.Scrollbar(wrapper, orient="vertical", command=canvas.yview)
    inner = tk.Frame(canvas, bg=bg_color)
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=scroll.set)
    canvas.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    return wrapper, canvas, inner

# ============================================================
# ЖИВОЙ ПРЕДПРОСМОТР ПРОПУСКА ТС — ФУНКЦИИ ОБЪЯВЛЕНЫ ДО ИНТЕРФЕЙСА
# (исправление NameError: кнопки ссылаются на schedule_auto_preview)
# ============================================================
_auto_preview_job = None

def schedule_auto_preview(*args, delay=150):
    global _auto_preview_job
    try:
        if _auto_preview_job is not None:
            root.after_cancel(_auto_preview_job)
        _auto_preview_job = root.after(delay, _render_auto_preview)
    except Exception:
        pass

def _get_preview_pass_data():
    use_second = auto_preview_target.get() == "2"
    if use_second:
        num_e, plate_v = p2_num, p2_plate_var
        brand_e, model_e, type_e, color_e = p2_brand, p2_model, p2_type, p2_color
        pos_e, fio_e, phone_e, terr_e = p2_d_pos, p2_d_fio, p2_d_phone, p2_territory
    else:
        num_e, plate_v = p1_num, p1_plate_var
        brand_e, model_e, type_e, color_e = p1_brand, p1_model, p1_type, p1_color
        pos_e, fio_e, phone_e, terr_e = p1_d_pos, p1_d_fio, p1_d_phone, p1_territory
    d_pos = pos_e.get().strip(); d_fio = fio_e.get().strip()
    driver_full = f"{d_pos} {d_fio}".strip() or "Должность  Фамилия И.О."
    try:
        issue_d = datetime.strptime(entry_issue.get().strip(), "%d.%m.%Y")
    except Exception:
        issue_d = datetime.now()
    try:
        valid_d = datetime.strptime(entry_valid.get().strip(), "%d.%m.%Y")
    except Exception:
        valid_d = add_years_safe(issue_d, 1)
    p = {"num": num_e.get().strip() or "000-00",
         "plate": plate_v.get().strip() or "А 000 АА 00",
         "brand": brand_e.get().strip(), "model": model_e.get().strip(),
         "type": type_e.get().strip(), "color": color_e.get().strip(),
         "d_pos": d_pos, "d_fio": d_fio, "phone": phone_e.get().strip(),
         "driver_full": driver_full, "territory": terr_e.get().strip()}
    common = {"issue_date": issue_d.strftime("%d.%m.%Y"), "valid_until": valid_d.strftime("%d.%m.%Y"),
              "otb_post": entry_otb_post.get().strip(), "otb_name": entry_otb_name.get().strip(),
              "is_temporary": is_temp_car_var.get()}
    return p, common

def _render_auto_preview():
    global _auto_preview_job
    _auto_preview_job = None
    try:
        if not os.path.exists(TEMPLATE_FILE):
            lbl_auto_preview.config(image="", text="⚠ Нет файла template.png\nв папке программы")
            return
        p, common = _get_preview_pass_data()
        img = render_pass(p, common, silent=True)
        panel_w = auto_preview_panel.winfo_width(); panel_h = auto_preview_panel.winfo_height()
        if panel_w < 80: panel_w = 480
        if panel_h < 120: panel_h = 460
        max_w = max(140, panel_w - 34); max_h = max(120, panel_h - 140)
        ratio = img.height / img.width
        w = min(max_w, 1600); h = int(w * ratio)
        if h > max_h:
            h = max_h; w = int(h / ratio)
        thumb = img.resize((max(80, w), max(60, h)), Image.Resampling.LANCZOS)
        photo_tk = ImageTk.PhotoImage(thumb)
        lbl_auto_preview.config(image=photo_tk, text="")
        lbl_auto_preview.image = photo_tk
    except Exception:
        pass

# ============================================================
# ВКЛАДКА 1: ПРОПУСК НА ТС
# ============================================================
auto_tab_container = ttk.Frame(main_notebook, padding="6")
main_notebook.add(auto_tab_container, text="   🚗  Пропуск на ТС (Авто)   ")

auto_btn_bar = tk.Frame(auto_tab_container, bg=CLR_BG)
auto_btn_bar.pack(side="bottom", fill="x", pady=(8, 0))
auto_row1 = tk.Frame(auto_btn_bar, bg=CLR_BG); auto_row1.pack(fill="x", pady=(0, 6))
tk.Button(auto_row1, text="💾  Сохранить PDF  (Ctrl+S)", command=generate_pass,
          bg=CLR_NAVY, fg="white", activebackground="#051627", activeforeground="white",
          font=F(11, True), pady=10, relief="flat", cursor="hand2").pack(side="left", fill="x", expand=True, padx=(0, 6))
tk.Button(auto_row1, text="🖨️  Напечатать сразу  (Ctrl+P)", command=direct_print_pass,
          bg="#007799", fg="white", activebackground="#005B77", activeforeground="white",
          font=F(11, True), pady=10, padx=18, relief="flat", cursor="hand2").pack(side="right")
auto_row2 = tk.Frame(auto_btn_bar, bg=CLR_BG); auto_row2.pack(fill="x")
tk.Button(auto_row2, text="📦 Массовая печать", command=open_batch_window, bg="#486581", fg="white",
          font=F(9, True), pady=7, padx=12, relief="flat", cursor="hand2").pack(side="left", padx=(0, 6))
tk.Button(auto_row2, text="📋 Реестр ТС для печати", command=generate_ts_registry_pdf, bg="#486581", fg="white",
          font=F(9, True), pady=7, padx=12, relief="flat", cursor="hand2").pack(side="left", padx=(0, 6))
tk.Button(auto_row2, text="📊 Журнал ТС", command=open_interactive_journal, bg="#334E68", fg="white",
          font=F(9, True), pady=7, padx=14, relief="flat", cursor="hand2").pack(side="right")

auto_paned = tk.PanedWindow(auto_tab_container, orient="horizontal", bg="#CBD2D9",
                            sashwidth=5, sashrelief="raised", borderwidth=0)
auto_paned.pack(side="top", fill="both", expand=True)
auto_left_wrapper = tk.Frame(auto_paned, bg=CLR_CARD)
auto_paned.add(auto_left_wrapper, minsize=420, width=700)
_, auto_canvas, auto_inner = make_scrollable(auto_left_wrapper, CLR_CARD)

auto_notebook = ttk.Notebook(auto_inner); auto_notebook.pack(fill="x", pady=(0, 6), padx=2)

def build_pass_tab(parent, default_num, is_second=False):
    tab = tk.Frame(parent, bg=CLR_CARD, padx=12, pady=8)
    f_top = tk.Frame(tab, bg=CLR_CARD); f_top.pack(fill="x", pady=(0, 4))
    tk.Label(f_top, text="Номер бланка:", font=F(9, True), bg=CLR_CARD, fg="#334E68").pack(side="left")
    e_num = ttk.Entry(f_top, width=12, font=F(10, True)); e_num.insert(0, default_num); e_num.pack(side="left", padx=(6, 12))
    if is_second:
        tk.Button(f_top, text="⚡ №1 + 1",
                  command=lambda: (e_num.delete(0, tk.END), e_num.insert(0, increment_number(p1_num.get())), schedule_auto_preview()),
                  bg="#E2E8F0", fg="#102A43", font=F(8, True), relief="flat", padx=6, cursor="hand2").pack(side="left", padx=(0, 15))
    tk.Label(f_top, text="Зона допуска:", font=F(9, True), bg=CLR_CARD, fg="#334E68").pack(side="left")
    cb_territory = ttk.Combobox(f_top, values=["", 'ПТО "Шаврова"', "Парковка", 'ПТО "Шаврова", Парковка'],
                                state="normal", font=F(9))
    cb_territory.set(settings["territory"] if not is_second else "")
    cb_territory.pack(side="left", fill="x", expand=True, padx=(6, 0))
    f_plate = tk.LabelFrame(tab, text=" Государственный регистрационный знак ТС ",
                            font=F(9, True), bg=CLR_CARD, fg=CLR_NAVY, padx=8, pady=4)
    f_plate.pack(fill="x", pady=(0, 4))
    plate_var = tk.StringVar()
    def force_caps(*args):
        val = plate_var.get()
        if val and val != val.upper():
            plate_var.set(val.upper())
        schedule_auto_preview()
    plate_var.trace_add("write", force_caps)
    e_plate = ttk.Entry(f_plate, textvariable=plate_var, font=F(13, True)); e_plate.pack(fill="x")
    f_row1 = tk.Frame(tab, bg=CLR_CARD); f_row1.pack(fill="x", pady=2)
    tk.Label(f_row1, text="Марка:", width=8, bg=CLR_CARD, anchor="w", fg="#486581", font=F(9)).pack(side="left")
    e_brand = ttk.Entry(f_row1, font=F(9)); e_brand.pack(side="left", fill="x", expand=True, padx=(0, 10))
    tk.Label(f_row1, text="Вид:", width=5, bg=CLR_CARD, anchor="w", fg="#486581", font=F(9)).pack(side="left")
    e_type = ttk.Entry(f_row1, font=F(9)); e_type.pack(side="left", fill="x", expand=True)
    f_row2 = tk.Frame(tab, bg=CLR_CARD); f_row2.pack(fill="x", pady=2)
    tk.Label(f_row2, text="Модель:", width=8, bg=CLR_CARD, anchor="w", fg="#486581", font=F(9)).pack(side="left")
    e_model = ttk.Entry(f_row2, font=F(9)); e_model.pack(side="left", fill="x", expand=True, padx=(0, 10))
    tk.Label(f_row2, text="Цвет:", width=5, bg=CLR_CARD, anchor="w", fg="#486581", font=F(9)).pack(side="left")
    e_color = ttk.Entry(f_row2, font=F(9)); e_color.pack(side="left", fill="x", expand=True)
    f_driver = tk.LabelFrame(tab, text=" Водитель (управляющий ТС) ", font=F(9, True), bg=CLR_CARD, fg=CLR_NAVY, padx=8, pady=4)
    f_driver.pack(fill="x", pady=(4, 2))
    r_d1 = tk.Frame(f_driver, bg=CLR_CARD); r_d1.pack(fill="x", pady=(0, 2))
    tk.Label(r_d1, text="Должность:", width=11, bg=CLR_CARD, anchor="w", fg="#486581", font=F(9)).pack(side="left")
    e_d_pos = ttk.Entry(r_d1, font=F(9)); e_d_pos.pack(side="left", fill="x", expand=True)
    r_d2 = tk.Frame(f_driver, bg=CLR_CARD); r_d2.pack(fill="x")
    tk.Label(r_d2, text="ФИО:", width=11, bg=CLR_CARD, anchor="w", fg="#486581", font=F(9)).pack(side="left")
    e_d_fio = ttk.Entry(r_d2, font=F(9)); e_d_fio.pack(side="left", fill="x", expand=True, padx=(0, 10))
    tk.Label(r_d2, text="Телефон:", bg=CLR_CARD, fg="#486581", font=F(9)).pack(side="left")
    e_d_phone = ttk.Entry(r_d2, width=17, font=F(9)); e_d_phone.pack(side="left", padx=(4, 0))
    e_plate.bind("<FocusOut>", lambda ev: auto_complete_car_fields(plate_var, e_brand, e_model, e_type, e_color,
                                                                   e_d_pos, e_d_fio, e_d_phone, cb_territory))
    return tab, e_num, plate_var, e_plate, e_brand, e_type, e_model, e_color, e_d_pos, e_d_fio, e_d_phone, cb_territory

tab1, p1_num, p1_plate_var, p1_plate_entry, p1_brand, p1_type, p1_model, p1_color, p1_d_pos, p1_d_fio, p1_d_phone, p1_territory = \
    build_pass_tab(auto_notebook, settings["last_pass_num"])
auto_notebook.add(tab1, text="  🚗 Пропуск №1 (Верхний)  ")
tab2, p2_num, p2_plate_var, p2_plate_entry, p2_brand, p2_type, p2_model, p2_color, p2_d_pos, p2_d_fio, p2_d_phone, p2_territory = \
    build_pass_tab(auto_notebook, increment_number(settings["last_pass_num"]), is_second=True)
auto_notebook.add(tab2, text="  🚙 Пропуск №2 (Нижний)  ")

common_box = tk.LabelFrame(auto_inner, text=" Реквизиты и ответственные лица ", font=F(9, True),
                           bg=CLR_CARD, fg=CLR_NAVY, padx=10, pady=6)
common_box.pack(fill="x", pady=(0, 6), padx=2)
row_dt = tk.Frame(common_box, bg=CLR_CARD); row_dt.pack(fill="x", pady=2)
tk.Label(row_dt, text="Дата выдачи:", bg=CLR_CARD, fg="#486581", font=F(9)).pack(side="left")
entry_issue = ttk.Entry(row_dt, width=13, font=F(9)); entry_issue.insert(0, settings["issue_date"]); entry_issue.pack(side="left", padx=(6, 16))
tk.Label(row_dt, text="Действителен до:", bg=CLR_CARD, fg="#486581", font=F(9)).pack(side="left")
entry_valid = ttk.Entry(row_dt, width=13, font=F(9)); entry_valid.insert(0, settings["valid_until"]); entry_valid.pack(side="left", padx=(6, 16))
is_temp_car_var = tk.BooleanVar(value=settings.get("is_temporary_car", False))

def on_toggle_temp_car():
    if is_temp_car_var.get():
        d_iss = validate_date_string(entry_issue.get(), "Дата выдачи")
        if d_iss:
            entry_valid.delete(0, tk.END)
            entry_valid.insert(0, add_months_safe(d_iss, 3).strftime("%d.%m.%Y"))
    schedule_auto_preview()
tk.Checkbutton(row_dt, text="⚠️ Временный пропуск на ТС (до 3 мес)", variable=is_temp_car_var,
               command=on_toggle_temp_car, bg=CLR_CARD, activebackground=CLR_CARD,
               font=F(9, True), fg="#C62828").pack(side="left")
row_otb = tk.Frame(common_box, bg=CLR_CARD); row_otb.pack(fill="x", pady=(4, 2))
tk.Label(row_otb, text="Должность ОТБ:", bg=CLR_CARD, fg="#486581", font=F(9)).pack(side="left")
entry_otb_post = ttk.Entry(row_otb, font=F(9)); entry_otb_post.insert(0, settings.get("otb_post", ""))
entry_otb_post.pack(side="left", fill="x", expand=True, padx=(6, 10))
tk.Label(row_otb, text="ФИО ОТБ:", bg=CLR_CARD, fg="#486581", font=F(9)).pack(side="left")
entry_otb_name = ttk.Entry(row_otb, width=18, font=F(9)); entry_otb_name.insert(0, settings.get("otb_name", ""))
entry_otb_name.pack(side="left", padx=(6, 0))

def update_tab_states():
    if print_mode_var.get() == "a5":
        auto_notebook.select(tab1); auto_notebook.tab(1, state="disabled")
    else:
        auto_notebook.tab(1, state="normal")

format_box = tk.LabelFrame(auto_inner, text=" Формат формирования ", font=F(9, True), bg=CLR_CARD, fg=CLR_NAVY, padx=10, pady=4)
format_box.pack(fill="x", pady=(0, 6), padx=2)
print_mode_var = tk.StringVar(value=settings["print_mode"])
tk.Radiobutton(format_box, text="📄 Лист А4: Два пропуска (№1 сверху, №2 снизу)", variable=print_mode_var,
               value="a4", command=update_tab_states, bg=CLR_CARD, activebackground=CLR_CARD, font=F(9)).pack(anchor="w")
tk.Radiobutton(format_box, text="📄 Лист А5: Один пропуск (вкладка №2 блокируется)", variable=print_mode_var,
               value="a5", command=update_tab_states, bg=CLR_CARD, activebackground=CLR_CARD, font=F(9)).pack(anchor="w")
tk.Label(auto_inner, text="Кнопки действий — в нижней панели вкладки (всегда видны).",
         bg=CLR_CARD, fg="#829AB1", font=F(8, italic=True)).pack(anchor="w", padx=6, pady=(0, 4))

auto_preview_panel = tk.LabelFrame(auto_paned, text=" ПРЕДПРОСМОТР ПРОПУСКА НА ТС ", font=F(11, True),
                                   bg="#FFFFFF", fg=CLR_NAVY, padx=12, pady=10)
auto_paned.add(auto_preview_panel, minsize=330, width=520)
preview_switch = tk.Frame(auto_preview_panel, bg="#FFFFFF"); preview_switch.pack(fill="x", pady=(0, 6))
tk.Label(preview_switch, text="Показывать:", bg="#FFFFFF", fg="#334E68", font=F(9, True)).pack(side="left")
auto_preview_target = tk.StringVar(value=settings.get("auto_preview_target", "1"))
tk.Radiobutton(preview_switch, text=" Пропуск №1", variable=auto_preview_target, value="1",
               bg="#FFFFFF", activebackground="#FFFFFF", font=F(9), command=schedule_auto_preview).pack(side="left", padx=4)
tk.Radiobutton(preview_switch, text=" Пропуск №2", variable=auto_preview_target, value="2",
               bg="#FFFFFF", activebackground="#FFFFFF", font=F(9), command=schedule_auto_preview).pack(side="left")
lbl_auto_preview = tk.Label(auto_preview_panel, bg="#FFFFFF", relief="solid", borderwidth=1,
                            text="Заполните поля —\nпредпросмотр появится здесь", fg="#829AB1", font=F(10))
lbl_auto_preview.pack(fill="both", expand=True, pady=(0, 8))
tk.Label(auto_preview_panel, text="Макет обновляется автоматически при вводе данных.\nРастяните разделитель или окно, чтобы увеличить превью.",
         bg="#FFFFFF", fg="#718096", font=F(8, italic=True), justify="center").pack()

def on_auto_preview_resize(event):
    schedule_auto_preview(delay=140)
auto_preview_panel.bind("<Configure>", on_auto_preview_resize)

# ============================================================
# ВКЛАДКА 2: БЕЙДЖ РАБОТНИКА
# ============================================================
badge_tab_container = ttk.Frame(main_notebook, padding="8")
main_notebook.add(badge_tab_container, text="   🪪  Постоянный пропуск для работников   ")

badge_btn_bar = tk.Frame(badge_tab_container, bg=CLR_BG)
badge_btn_bar.pack(side="bottom", fill="x", pady=(8, 0))
badge_row1 = tk.Frame(badge_btn_bar, bg=CLR_BG); badge_row1.pack(fill="x", pady=(0, 6))
tk.Button(badge_row1, text="💾  Сохранить PDF  (Ctrl+S)", command=generate_badge_pdf,
          bg=CLR_NAVY, fg="white", activebackground="#051627", activeforeground="white",
          font=F(11, True), pady=10, relief="flat", cursor="hand2").pack(side="left", fill="x", expand=True, padx=(0, 6))
tk.Button(badge_row1, text="🖨️  Напечатать сразу  (Ctrl+P)", command=direct_print_badge,
          bg="#007799", fg="white", activebackground="#005B77", activeforeground="white",
          font=F(11, True), pady=10, padx=18, relief="flat", cursor="hand2").pack(side="right")
badge_row2 = tk.Frame(badge_btn_bar, bg=CLR_BG); badge_row2.pack(fill="x")
tk.Button(badge_row2, text="📦 Массовая печать", command=open_badge_batch_window, bg="#486581", fg="white",
          font=F(9, True), pady=7, padx=12, relief="flat", cursor="hand2").pack(side="left", padx=(0, 6))
tk.Button(badge_row2, text="📋 Реестр работников", command=generate_employee_registry_pdf, bg="#486581", fg="white",
          font=F(9, True), pady=7, padx=12, relief="flat", cursor="hand2").pack(side="left", padx=(0, 6))
tk.Button(badge_row2, text="📊 Журнал бейджей", command=open_badge_journal, bg="#334E68", fg="white",
          font=F(9, True), pady=7, padx=14, relief="flat", cursor="hand2").pack(side="right")

badge_paned = tk.PanedWindow(badge_tab_container, orient="horizontal", bg="#CBD2D9",
                             sashwidth=5, sashrelief="raised", borderwidth=0)
badge_paned.pack(side="top", fill="both", expand=True)
b_left_wrapper = tk.Frame(badge_paned, bg=CLR_BG)
badge_paned.add(b_left_wrapper, minsize=420, width=680)
_, b_canvas, b_left_panel = make_scrollable(b_left_wrapper, CLR_BG)

b_card = tk.LabelFrame(b_left_panel, text=" Данные сотрудника ", font=F(10, True), bg=CLR_CARD, fg=CLR_NAVY, padx=12, pady=8)
b_card.pack(fill="both", expand=True, pady=(0, 6), padx=4)
b_row0 = tk.Frame(b_card, bg=CLR_CARD); b_row0.pack(fill="x", pady=(0, 6))
tk.Label(b_row0, text="Подразделение:", font=F(9, True), bg=CLR_CARD, fg="#334E68").pack(side="left")
badge_park_cb = ttk.Combobox(b_row0, values=["ОСП «Трамвайный парк № 8»", "ОСП «Трамвайный парк № 5»",
                                             "ОСП «Трамвайный парк № 7»", "ОСП «Троллейбусный парк № 1»", 'ПТО "Шаврова"'],
                             state="normal", font=F(9))
badge_park_cb.set(settings.get("badge_park", "ОСП «Трамвайный парк № 8»"))
badge_park_cb.pack(side="left", fill="x", expand=True, padx=(6, 12))
badge_park_cb.bind("<<ComboboxSelected>>", update_badge_preview)
badge_park_cb.bind("<KeyRelease>", update_badge_preview)
tk.Label(b_row0, text="Табельный №:", font=F(9, True), bg=CLR_CARD, fg="#334E68").pack(side="left")
b_tab_num_ent = ttk.Entry(b_row0, width=9, font=F(10, True))
b_tab_num_ent.insert(0, settings.get("badge_tab_num", "01035"))
b_tab_num_ent.pack(side="left", padx=(6, 0)); b_tab_num_ent.bind("<KeyRelease>", update_badge_preview)
b_row_role = tk.Frame(b_card, bg=CLR_CARD); b_row_role.pack(fill="x", pady=(0, 6))
tk.Label(b_row_role, text="Должность:", font=F(9, True), bg=CLR_CARD, fg="#334E68").pack(side="left")
b_role_ent = ttk.Entry(b_row_role, font=F(10)); b_role_ent.pack(side="left", fill="x", expand=True, padx=(6, 0))
b_role_ent.bind("<KeyRelease>", update_badge_preview)

b_sur_var = tk.StringVar(); b_nam_var = tk.StringVar(); b_pat_var = tk.StringVar()
def make_upper_callback_with_preview(var):
    def cb(*a):
        val = var.get()
        if val and val != val.upper():
            var.set(val.upper())
        update_badge_preview()
    return cb
b_sur_var.trace_add("write", make_upper_callback_with_preview(b_sur_var))
b_nam_var.trace_add("write", make_upper_callback_with_preview(b_nam_var))
b_pat_var.trace_add("write", make_upper_callback_with_preview(b_pat_var))

b_sur_ent = ttk.Entry(b_card, textvariable=b_sur_var, font=F(11, True))
b_nam_ent = ttk.Entry(b_card, textvariable=b_nam_var, font=F(11, True))
b_pat_ent = ttk.Entry(b_card, textvariable=b_pat_var, font=F(11, True))
tk.Label(b_card, text="Фамилия сотрудника:", font=F(9, True), bg=CLR_CARD, fg="#486581").pack(anchor="w")
b_sur_ent.pack(fill="x", pady=(1, 4))
tk.Label(b_card, text="Имя сотрудника:", font=F(9, True), bg=CLR_CARD, fg="#486581").pack(anchor="w")
b_nam_ent.pack(fill="x", pady=(1, 4))
tk.Label(b_card, text="Отчество сотрудника:", font=F(9, True), bg=CLR_CARD, fg="#486581").pack(anchor="w")
b_pat_ent.pack(fill="x", pady=(1, 4))
tk.Label(b_card, text="Телефон (для базы и КПП):", font=F(9), bg=CLR_CARD, fg="#486581").pack(anchor="w")
b_phone_ent = ttk.Entry(b_card, font=F(10)); b_phone_ent.pack(fill="x", pady=(1, 6))
b_photo_action_row = tk.Frame(b_card, bg=CLR_CARD); b_photo_action_row.pack(fill="x", pady=(0, 6))
tk.Button(b_photo_action_row, text="📷 Выбрать фото и обрезать (зум + сдвиг)", command=select_badge_photo,
          bg=CLR_NAVY, fg="white", font=F(9, True), relief="flat", padx=10, pady=6, cursor="hand2").pack(side="left")
lbl_photo_status = tk.Label(b_photo_action_row, text="Фото не выбрано", font=F(8), bg=CLR_CARD, fg="#C62828")
lbl_photo_status.pack(side="left", padx=(10, 0))
b_date_box = tk.LabelFrame(b_card, text=" Срок действия (постоянный: 5 лет) ", font=F(9, True), bg=CLR_CARD, fg=CLR_NAVY, padx=8, pady=6)
b_date_box.pack(fill="x", pady=(2, 6))
b_dt_row = tk.Frame(b_date_box, bg=CLR_CARD); b_dt_row.pack(fill="x")
today_now = datetime.now()
tk.Label(b_dt_row, text="Выдан:", font=F(9, True), bg=CLR_CARD, fg="#486581").pack(side="left")
b_issue_ent = ttk.Entry(b_dt_row, width=11, font=F(9)); b_issue_ent.insert(0, today_now.strftime("%d.%m.%Y"))
b_issue_ent.pack(side="left", padx=(4, 10)); b_issue_ent.bind("<KeyRelease>", update_badge_preview)
tk.Label(b_dt_row, text="До:", font=F(9, True), bg=CLR_CARD, fg="#486581").pack(side="left")
b_valid_ent = ttk.Entry(b_dt_row, width=11, font=F(9, True))
b_valid_ent.insert(0, add_years_safe(today_now, 5).strftime("%d.%m.%Y"))
b_valid_ent.pack(side="left", padx=(4, 10)); b_valid_ent.bind("<KeyRelease>", update_badge_preview)

def set_badge_years(y_count):
    d_iss = validate_date_string(b_issue_ent.get(), "Выдан")
    if d_iss:
        b_valid_ent.delete(0, tk.END)
        b_valid_ent.insert(0, add_years_safe(d_iss, y_count).strftime("%d.%m.%Y"))
        update_badge_preview()
tk.Button(b_dt_row, text="+ 5 лет", command=lambda: set_badge_years(5), bg="#E2E8F0", fg="#0A2540",
          font=F(8, True), relief="flat", padx=6, pady=2, cursor="hand2").pack(side="left", padx=(0, 4))
tk.Button(b_dt_row, text="+ 1 год", command=lambda: set_badge_years(1), bg="#E2E8F0", fg="#486581",
          font=F(8), relief="flat", padx=6, pady=2, cursor="hand2").pack(side="left")
b_fmt_box = tk.LabelFrame(b_card, text=" Формат формирования ", font=F(9, True), bg=CLR_CARD, fg=CLR_NAVY, padx=8, pady=4)
b_fmt_box.pack(fill="x", pady=(2, 0))
badge_print_mode_var = tk.StringVar(value=settings.get("badge_print_mode", "card"))
for txt, val in [("🪪 Пластиковая карта (85 × 54 мм) — карточный принтер", "card"),
                 ("📄 Лист А4 (сетка 3×3, 9 бейджей) — для нарезки резаком", "a4_grid"),
                 ("📄 Лист А4 (1 бейдж по центру) — тестовый лист", "a4_single")]:
    tk.Radiobutton(b_fmt_box, text=txt, variable=badge_print_mode_var, value=val,
                   bg=CLR_CARD, activebackground=CLR_CARD, font=F(9)).pack(anchor="w")
tk.Label(b_left_panel, text="Кнопки действий — в нижней панели вкладки (всегда видны).",
         bg=CLR_BG, fg="#829AB1", font=F(8, italic=True)).pack(anchor="w", padx=6, pady=(0, 4))

b_right_preview_panel = tk.LabelFrame(badge_paned, text=" ПРЕДПРОСМОТР БЕЙДЖА (85 × 54 мм) ", font=F(11, True),
                                      bg="#FFFFFF", fg=CLR_NAVY, padx=14, pady=12)
badge_paned.add(b_right_preview_panel, minsize=330, width=520)
lbl_badge_live_preview = tk.Label(b_right_preview_panel, bg="#FFFFFF", relief="solid", borderwidth=1,
                                  text="Предпросмотр загружается...", fg="#829AB1", font=F(10))
lbl_badge_live_preview.pack(fill="both", expand=True, pady=(0, 8))
tk.Label(b_right_preview_panel, text="Макет обновляется на лету при изменении любых полей.\nРастяните разделитель или окно — превью увеличится.",
         bg="#FFFFFF", fg="#718096", font=F(8, italic=True), justify="center").pack()

def on_badge_preview_resize(event):
    update_badge_preview(delay=140)
b_right_preview_panel.bind("<Configure>", on_badge_preview_resize)

# ============================================================
# ГОРЯЧИЕ КЛАВИШИ И СТАРТ
# ============================================================
def on_ctrl_shortcuts(event):
    current_tab = main_notebook.index(main_notebook.select())
    if event.keysym in ('s', 'S', 'Cyrillic_yeru', 'Cyrillic_YERU') or event.char in ('\x13',):
        if current_tab == 0: generate_pass()
        else: generate_badge_pdf()
        return "break"
    if event.keysym in ('p', 'P', 'Cyrillic_ze', 'Cyrillic_ZE') or event.char in ('\x10',):
        if current_tab == 0: direct_print_pass()
        else: direct_print_badge()
        return "break"
root.bind_all("<Control-KeyPress>", on_ctrl_shortcuts)

update_tab_states()

def bind_auto_preview(widgets, comboboxes=()):
    for w in widgets:
        try:
            w.bind("<KeyRelease>", schedule_auto_preview, add="+")
        except Exception:
            pass
    for cb in comboboxes:
        try:
            cb.bind("<<ComboboxSelected>>", schedule_auto_preview, add="+")
            cb.bind("<KeyRelease>", schedule_auto_preview, add="+")
        except Exception:
            pass

bind_auto_preview(
    [p1_num, p1_plate_entry, p1_brand, p1_type, p1_model, p1_color, p1_d_pos, p1_d_fio, p1_d_phone,
     p2_num, p2_plate_entry, p2_brand, p2_type, p2_model, p2_color, p2_d_pos, p2_d_fio, p2_d_phone,
     entry_issue, entry_valid, entry_otb_post, entry_otb_name],
    comboboxes=[p1_territory, p2_territory]
)

def initial_previews():
    update_badge_preview(delay=10)
    schedule_auto_preview(delay=20)

root.after(250, initial_previews)
p1_plate_entry.focus()
root.mainloop()