"""Массовая печать из CSV."""
from __future__ import annotations

import csv
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import ImageDraw

from getpass_core import render as R
from getpass_core import issuance
from getpass_core.printing import save_pdf_pages
from getpass_core.storage import FileBusy
from getpass_core.importing import photo_in_folder, validate_items

from .components import section_title
from .theme import Card
from .widgets import ProgressDialog

PASS_TEMPLATE_HEADER = ["Номер пропуска", "Госномер", "Марка", "Модель", "Вид", "Цвет",
                        "Должность водителя", "ФИО водителя", "Телефон", "Зона допуска"]
PASS_TEMPLATE_SAMPLE = ["001-26", "О 777 ТВ 198", "ГАЗ", "Газель NEXT", "Служебный", "Белый",
                        "Водитель 1-го класса", "Смирнов А.В.", "+7 (921) 111-22-33",
                        'ПТО "Шаврова"']
BADGE_TEMPLATE_HEADER = ["Табельный номер", "Фамилия", "Имя", "Отчество", "Должность",
                         "Подразделение", "Телефон", "Имя_файла_фото", "Дата выдачи",
                         "Действителен до"]
BADGE_TEMPLATE_SAMPLE = ["01035", "ИВАНОВ", "ИВАН", "ИВАНОВИЧ", "Водитель трамвая",
                         "ОСП «Трамвайный парк № 8»", "+7 (921) 123-45-67", "ivanov.jpg",
                         "", ""]


def export_template(header, sample, initial_name, note=""):
    path = filedialog.asksaveasfilename(defaultextension=".csv",
                                        filetypes=[("CSV", "*.csv")],
                                        initialfile=initial_name)
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(header)
            writer.writerow(sample)
    except Exception as exc:
        messagebox.showerror("Ошибка", f"Не удалось сохранить шаблон:\n{exc}")
        return
    messagebox.showinfo("Шаблон сохранён", f"Заполните файл в Excel:\n{path}{note}")


def read_csv_rows(title):
    path = filedialog.askopenfilename(title=title,
                                      filetypes=[("CSV", "*.csv"), ("Все файлы", "*.*")])
    if not path:
        return None, None
    rows = []
    # Попытка прочитать в UTF-8, при неудаче — Windows-1251 (стандарт Excel)
    encodings = ("utf-8-sig", "cp1251", "utf-8")
    for enc in encodings:
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                rows = list(csv.reader(f, delimiter=";"))
            break
        except UnicodeDecodeError:
            continue
        except Exception as exc:
            messagebox.showerror("Ошибка чтения", f"Не удалось прочитать файл: {exc}")
            return None, None
    else:
        messagebox.showerror("Ошибка кодировки", "Не удалось распознать кодировку файла (требуется UTF-8 или CP1251).")
        return None, None

    return path, rows[1:] if len(rows) > 1 else []


def run_batch(parent, theme, title, items, page_builder, pages_total, journal,
              log_records, default_name):
    if not review_import(parent, theme, items, journal):
        return False
    save_path = filedialog.asksaveasfilename(defaultextension=".pdf",
                                             filetypes=[("PDF", "*.pdf")],
                                             initialfile=default_name)
    if not save_path:
        return False

    class Cancelled(Exception):
        pass

    def pages():
        with ProgressDialog(parent, theme, title, pages_total) as dlg:
            for idx, page in enumerate(page_builder(), start=1):
                if dlg.cancelled:
                    raise Cancelled()
                dlg.step(idx, f"Готовится лист {idx} из {pages_total}...")
                if dlg.cancelled:
                    raise Cancelled()
                yield page

    try:
        operation_id = issuance.prepare(journal, log_records, save_path)
        save_pdf_pages(pages(), save_path)
    except Cancelled:
        messagebox.showinfo("Отменено", "Массовая печать прервана. Прежний файл сохранён.", parent=parent)
        return False
    except ValueError:
        messagebox.showwarning("Пусто", "Нечего печатать.", parent=parent)
        return False
    except Exception as exc:
        messagebox.showerror("Ошибка", f"Не удалось сохранить PDF:\n{exc}", parent=parent)
        return False

    try:
        issuance.confirm(journal, operation_id)
    except FileBusy as exc:
        messagebox.showerror(
            "Журнал не обновлён",
            f"PDF сохранён, но «{os.path.basename(exc.path)}» занят другой программой.\n"
            f"Закройте его и повторите — записи ({len(log_records)} шт.) не попали в журнал.",
            parent=parent)
        return False
    except Exception as exc:
        messagebox.showerror("Журнал не обновлён",
                             f"PDF сохранён, но журнал не записан:\n{exc}", parent=parent)
        return False

    if messagebox.askyesno("Готово", f"Обработано записей: {len(items)}.\n\nОткрыть файл?",
                           parent=parent):
        try:
            os.startfile(save_path)  # noqa: Windows only
        except Exception:
            pass
    return True


def review_import(parent, theme, items, journal):
    results = validate_items(items, journal, badge="tab_num" in journal.schema.keys)
    win = theme.toplevel(parent, "Проверка импорта")
    win.geometry("1000x600")
    win.transient(parent)
    win.grab_set()
    errors = sum(bool(e) for _, e, _ in results)
    warnings = sum(bool(w) for _, _, w in results)
    ttk.Label(win, text=f"Записей: {len(items)} · С ошибками: {errors} · Предупреждений: {warnings}").pack(pady=12)
    tree = ttk.Treeview(win, columns=("row", "number", "person", "result"), show="headings")
    for key, title, width in (("row", "Строка", 60), ("number", "Номер", 120),
                              ("person", "Сотрудник / водитель", 220), ("result", "Проверка", 450)):
        tree.heading(key, text=title)
        tree.column(key, width=width)
    scroll = ttk.Scrollbar(win, command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    scroll.pack(side="right", fill="y")
    tree.pack(fill="both", expand=True, padx=12)
    tree.tag_configure("error", foreground=theme.c("danger"))
    for item, (row, err, warn) in zip(items, results):
        tree.insert("", "end", values=(row, item.get("tab_num", item.get("plate", "")),
                    item.get("fio", item.get("driver_full", "")), "; ".join(err + warn) or "Готово"),
                    tags=("error",) if err else ())
    def save_report():
        path = filedialog.asksaveasfilename(parent=win, defaultextension=".csv",
            filetypes=[("CSV", "*.csv")], initialfile="отчёт_импорта.csv")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.writer(stream, delimiter=";")
                writer.writerow(["Строка", "Номер", "Ошибки", "Предупреждения"])
                for item, (row, err, warn) in zip(items, results):
                    writer.writerow([row, item.get("tab_num", item.get("plate", "")),
                                     " | ".join(err), " | ".join(warn)])
            messagebox.showinfo("Отчёт сохранён", path, parent=win)
        except OSError as exc:
            messagebox.showerror("Ошибка", f"Не удалось сохранить отчёт:\n{exc}", parent=win)
    accepted = [False]
    def proceed():
        if warnings and not messagebox.askyesno("Подтвердить предупреждения",
                "Есть совпадения с журналом или чёрным списком. Продолжить выдачу?", parent=win):
            return
        accepted[0] = True
        win.destroy()
    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=12, pady=12)
    ttk.Button(bar, text="Вернуться и исправить CSV", command=win.destroy).pack(side="left")
    ttk.Button(bar, text="Сохранить отчёт", command=save_report).pack(side="left", padx=8)
    ttk.Button(bar, text="Сформировать PDF", command=proceed,
               state="disabled" if errors else "normal").pack(side="right")
    parent.wait_window(win)
    return accepted[0]


def parse_pass_rows(rows, common):
    items = []
    for r in rows:
        if len(r) < 2 or not r[1].strip():
            continue
        def cell(i, default=""):
            return r[i].strip() if len(r) > i else default
        pos, fio = cell(6), cell(7)
        items.append({
            "num": cell(0), "plate": cell(1), "brand": cell(2), "model": cell(3),
            "type": cell(4, "Служебный"), "color": cell(5),
            "d_pos": pos, "d_fio": fio, "phone": cell(8),
            "driver_full": f"{pos} {fio}".strip(), "territory": cell(9),
            **common,
        })
    return items


def parse_badge_rows(rows, folder, defaults):
    items = []
    for r in rows:
        if len(r) < 4 or not r[1].strip():
            continue
        def cell(i, default=""):
            return r[i].strip() if len(r) > i else default
        photo = cell(7)
        photo_path = photo_in_folder(folder, photo)
        if not os.path.exists(photo_path):
            photo_path = ""
        sur, nam, pat = cell(1), cell(2), cell(3)
        items.append({
            "tab_num": cell(0), "surname": sur, "name": nam, "patronymic": pat,
            "fio": " ".join(p for p in (sur, nam, pat) if p),
            "role": cell(4, "Сотрудник"), "park": cell(5) or defaults["park"],
            "phone": cell(6), "photo_path": photo_path,
            "issue_date": cell(8) or defaults["issue_date"],
            "valid_until": cell(9) or defaults["valid_until"],
        })
    return items


def pass_pages(items, common):
    for i in range(0, len(items), 2):
        img1 = R.render_pass(items[i], common)
        img2 = R.render_pass(items[i + 1], common) if i + 1 < len(items) else None
        sheet = R.build_pass_a4_sheet(img1, img2)
        draw = ImageDraw.Draw(sheet)
        R.draw_sheet_brand_icons(draw, 140, 52, size=44)
        yield sheet


def badge_pages(items):
    per_page = 9
    for start in range(0, len(items), per_page):
        chunk = [R.render_single_badge_image(it) for it in items[start:start + per_page]]
        yield R.build_badge_a4_grid(chunk)


def open_batch_dialog(parent, theme, title, intro, on_template, on_run):
    th = theme
    win = th.toplevel(parent, title, resizable=(False, False))
    w, h = int(560 * th.scale), int(320 * th.scale)
    win.geometry(f"{w}x{h}")
    win.grab_set()
    card = Card(win, th)
    card.pack(fill="both", expand=True, padx=th.sp(3), pady=th.sp(3))
    b = card.body
    section_title(b, th, title).pack(anchor="w", pady=(0, th.sp(3)))
    tk.Label(b, text=intro, bg=th.c("surface"), fg=th.c("ink_muted"),
             font=th.font("body"), justify="left").pack(anchor="w", pady=(0, th.sp(4)))
    ttk.Button(b, text="1. Скачать пустой шаблон (CSV)", command=on_template,
               style="Ghost.TButton").pack(fill="x", pady=(0, th.sp(2)))
    ttk.Button(b, text="2. Выбрать файл и напечатать массово",
               command=lambda: (win.destroy(), on_run()),
               style="Primary.TButton").pack(fill="x")
    tk.Label(b, text="Печать можно прервать кнопкой «Отмена» в окне прогресса.",
             bg=th.c("surface"), fg=th.c("ink_faint"), font=th.font("caption")
             ).pack(anchor="w", pady=(th.sp(3), 0))
    card.fit()
