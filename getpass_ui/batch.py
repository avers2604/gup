"""Массовая печать из CSV — общий каркас для пропусков ТС и бейджей."""
from __future__ import annotations

import csv
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import ImageDraw

from getpass_core import render as R
from getpass_core.printing import save_pdf_pages
from getpass_core.storage import FileBusy

from .widgets import CLR_BG, F, ProgressDialog, styled_button

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
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f, delimiter=";"))
    except Exception as exc:
        messagebox.showerror("Ошибка чтения", f"Не удалось прочитать файл: {exc}")
        return None, None
    return path, rows[1:] if len(rows) > 1 else []


def run_batch(parent, title, items, page_builder, pages_total, journal,
              log_records, default_name):
    """Общий сценарий: выбрать файл, отрисовать, записать PDF и журнал.

    Страницы отдаются генератором и не копятся в памяти: лист А4 в 300 dpi
    занимает ~25 МБ, и сотня листов раньше означала 2.5 ГБ до записи файла.
    """
    save_path = filedialog.asksaveasfilename(defaultextension=".pdf",
                                             filetypes=[("PDF", "*.pdf")],
                                             initialfile=default_name)
    if not save_path:
        return False

    cancelled = {"flag": False}

    def pages():
        with ProgressDialog(parent, title, pages_total) as dlg:
            for idx, page in enumerate(page_builder(), start=1):
                if dlg.cancelled:
                    cancelled["flag"] = True
                    return
                dlg.step(idx, f"Готовится лист {idx} из {pages_total}...")
                yield page

    try:
        save_pdf_pages(pages(), save_path)
    except ValueError:
        if cancelled["flag"]:
            messagebox.showinfo("Отменено", "Массовая печать прервана.", parent=parent)
            return False
        messagebox.showwarning("Пусто", "Нечего печатать.", parent=parent)
        return False
    except Exception as exc:
        messagebox.showerror("Ошибка", f"Не удалось сохранить PDF:\n{exc}", parent=parent)
        return False

    if cancelled["flag"]:
        messagebox.showinfo("Отменено",
                            "Печать прервана. Частичный файл сохранён, "
                            "в журнал ничего не записано.", parent=parent)
        return False

    try:
        journal.append_many(log_records)
    except FileBusy as exc:
        messagebox.showerror(
            "Журнал не обновлён",
            f"PDF сохранён, но «{os.path.basename(exc.path)}» занят другой программой.\n"
            f"Закройте его и повторите — записи ({len(log_records)} шт.) не попали в журнал.",
            parent=parent)
    except Exception as exc:
        messagebox.showerror("Журнал не обновлён",
                             f"PDF сохранён, но журнал не записан:\n{exc}", parent=parent)

    if messagebox.askyesno("Готово", f"Обработано записей: {len(items)}.\n\nОткрыть файл?",
                           parent=parent):
        try:
            os.startfile(save_path)  # noqa: Windows only
        except Exception:
            pass
    return True


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
        photo_path = os.path.join(folder, photo) if photo else ""
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
    """Листы А4 по два пропуска. Нечётный остаток — один пропуск, без дубля."""
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


def open_batch_dialog(parent, title, intro, on_template, on_run):
    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry("560x290")
    win.transient(parent)
    win.grab_set()
    frame = ttk.Frame(win, padding="20")
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text=title, font=F(11, True)).pack(anchor="w", pady=(0, 10))
    ttk.Label(frame, text=intro, justify="left").pack(anchor="w", pady=(0, 15))
    tk.Button(frame, text="📥 1. Скачать пустой шаблон (CSV)", command=on_template,
              bg="#ECEFF1", font=F(10), pady=6, relief="groove",
              cursor="hand2").pack(fill="x", pady=4)
    styled_button(frame, "🚀 2. Выбрать файл и напечатать массово",
                  lambda: (win.destroy(), on_run()), "#0A2540",
                  font=F(10, True), pady=8).pack(fill="x", pady=6)
    tk.Label(frame, text="Печать можно прервать кнопкой «Отмена» в окне прогресса.",
             bg=CLR_BG, fg="#829AB1", font=F(8, italic=True)).pack(anchor="w", pady=(8, 0))
