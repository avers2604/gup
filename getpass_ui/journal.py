"""Окно журнала выданных документов."""
from __future__ import annotations

import os
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, simpledialog, ttk

from getpass_core import blacklist
from getpass_core.domain import parse_date
from getpass_core.storage import STATUS_REVOKED, FileBusy, export_records_to_xlsx

from .components import Field, section_title
from .theme import Theme
from .tokens import darken, lighten
from .widgets import make_scrollable

_EXTRA_FILTERS = {
    "zone": ("combobox", "Зона допуска"),
    "park": ("combobox", "Подразделение"),
    "role": ("combobox", "Должность"),
    "driver": ("entry", "Водитель"),
}


def open_journal_window(parent, journal, title, theme: Theme):
    JournalWindow(parent, journal, title, theme)


class JournalWindow:
    def __init__(self, parent, journal, title, theme: Theme):
        self.journal = journal
        self.schema = journal.schema
        self.theme = theme
        self.records = journal.read()
        self.sort_key = None
        self.sort_reverse = False
        self._extra_widgets = {}

        th = theme
        self.win = th.toplevel(parent, title)
        w, h = int(1280 * th.scale), int(700 * th.scale)
        self.win.geometry(f"{w}x{h}")
        self.win.minsize(int(980 * th.scale), int(480 * th.scale))

        self._build_filters()
        self._build_tree()
        self._build_buttons()
        self.apply_filter()

    def _build_filters(self):
        th = self.theme
        bar = tk.Frame(self.win, bg=th.c("ground"))
        bar.pack(fill="x", padx=th.sp(3), pady=(th.sp(3), 0))

        row1 = tk.Frame(bar, bg=th.c("ground"))
        row1.pack(fill="x", pady=(0, th.sp(2)))
        self.search_field = Field(row1, th, "Поиск")
        self.search_field.pack(side="left", padx=(0, th.sp(4)))
        self.search_field.configure_field(width=28)
        self.search_var = tk.StringVar()
        self.search_field.widget.configure(textvariable=self.search_var)

        status_box = tk.Frame(row1, bg=th.c("ground"))
        status_box.pack(side="left")
        section_title(status_box, th, "Статус").pack(anchor="w")
        radios = tk.Frame(status_box, bg=th.c("ground"))
        radios.pack(anchor="w", pady=(th.sp(1), 0))
        self.filter_var = tk.StringVar(value="active")
        for text, value in (("Все", "all"), ("Действующие", "active"),
                            ("Просроченные", "expired"), ("Аннулированные", "revoked"),
                            ("Без срока", "unknown")):
            th.radio(radios, text, self.filter_var, value).pack(side="left",
                                                                 padx=(0, th.sp(2)))

        row2 = tk.Frame(bar, bg=th.c("ground"))
        row2.pack(fill="x", pady=(0, th.sp(2)))
        self.date_from = Field(row2, th, "Дата выдачи с", width=11)
        self.date_from.pack(side="left", padx=(0, th.sp(2)))
        self.date_to = Field(row2, th, "по", width=11)
        self.date_to.pack(side="left", padx=(0, th.sp(4)))

        for key, (kind, label) in _EXTRA_FILTERS.items():
            if key not in self.schema.keys:
                continue
            if kind == "combobox":
                values = [""] + self.journal.distinct(key)
                field = Field(row2, th, label, kind="combobox", values=values)
                field.set("")
            else:
                field = Field(row2, th, label, width=20)
            field.pack(side="left", padx=(0, th.sp(3)))
            field.bind("<KeyRelease>", self.apply_filter, add="+")
            field.bind("<<ComboboxSelected>>", self.apply_filter, add="+")
            self._extra_widgets[key] = field

        self.search_var.trace_add("write", self.apply_filter)
        self.filter_var.trace_add("write", self.apply_filter)
        self.date_from.bind("<KeyRelease>", self.apply_filter, add="+")
        self.date_to.bind("<KeyRelease>", self.apply_filter, add="+")

    def _build_tree(self):
        th = self.theme
        frame = tk.Frame(self.win, bg=th.c("ground"))
        frame.pack(fill="both", expand=True, padx=th.sp(3), pady=th.sp(2))
        self.visible_fields = [f for f in self.schema.fields if f.tree_width > 0]
        columns = [f.key for f in self.visible_fields]
        self.tree = ttk.Treeview(frame, columns=columns, show="headings",
                                 selectmode="extended")
        for f in self.visible_fields:
            self.tree.heading(f.key, text=f.title,
                              command=lambda k=f.key: self._sort_by(k))
            self.tree.column(f.key, width=th.px(f.tree_width), anchor=f.anchor)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.tag_configure("revoked", foreground=th.c("ink_faint"))
        self.tree.tag_configure("expired", foreground=th.c("danger"))
        self.tree.tag_configure("unknown", background=th.c("surface_alt"))
        # Тонированная плашка вместо сплошного текста фирменным салатовым —
        # у чистого success на светлом фоне недостаточный контраст для текста.
        if th.is_dark:
            self.tree.tag_configure("active", background=darken(th.c("success"), 0.82),
                                    foreground=lighten(th.c("success"), 0.15))
        else:
            self.tree.tag_configure("active", background=lighten(th.c("success"), 0.82),
                                    foreground=darken(th.c("success"), 0.55))
        self.tree.bind("<Double-1>", lambda e: self.edit_selected())

    def _build_buttons(self):
        th = self.theme
        bar = tk.Frame(self.win, bg=th.c("ground"))
        bar.pack(fill="x", padx=th.sp(3), pady=(0, th.sp(3)))
        self.status = tk.Label(bar, bg=th.c("ground"), fg=th.c("ink_muted"),
                               font=th.font("caption"))
        self.status.pack(side="left")
        ttk.Button(bar, text="Изменить", command=self.edit_selected,
                   style="Ghost.TButton").pack(side="left", padx=(th.sp(4), th.sp(2)))
        ttk.Button(bar, text="Открыть в Excel", command=self.open_excel,
                   style="Ghost.TButton").pack(side="right")
        ttk.Button(bar, text="Удалить", command=self.delete_selected,
                   style="Danger.TButton").pack(side="right", padx=(0, th.sp(2)))
        ttk.Button(bar, text="Аннулировать", command=self.revoke_selected,
                   style="Ghost.TButton").pack(side="right", padx=(0, th.sp(2)))

    def _sort_by(self, key):
        if self.sort_key == key:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_key, self.sort_reverse = key, False
        self.records.sort(key=lambda r: (r.get(key) or "").lower(),
                          reverse=self.sort_reverse)
        for f in self.visible_fields:
            arrow = ""
            if f.key == self.sort_key:
                arrow = "  ▼" if self.sort_reverse else "  ▲"
            self.tree.heading(f.key, text=f.title + arrow)
        self.apply_filter()

    def apply_filter(self, *_args):
        query = self.search_var.get().lower().strip()
        mode = self.filter_var.get()
        d_from = parse_date(self.date_from.get())
        d_to = parse_date(self.date_to.get())
        extras = {k: w.get().strip() for k, w in self._extra_widgets.items()}
        today = datetime.now().date()
        self.tree.delete(*self.tree.get_children())
        shown = 0
        for rec in self.records:
            if query and not any(query in str(v).lower() for v in rec.values()):
                continue
            state = self._state_of(rec, today)
            if mode != "all" and state != mode:
                continue
            issue = parse_date(rec.get("issue_date"))
            if d_from and (issue is None or issue.date() < d_from.date()):
                continue
            if d_to and (issue is None or issue.date() > d_to.date()):
                continue
            skip = False
            for key, val in extras.items():
                if not val:
                    continue
                cell = (rec.get(key) or "")
                kind = _EXTRA_FILTERS[key][0]
                if kind == "combobox":
                    if cell != val:
                        skip = True
                        break
                elif val.lower() not in cell.lower():
                    skip = True
                    break
            if skip:
                continue
            values = [self._display(rec, f.key, state) for f in self.visible_fields]
            self.tree.insert("", "end", iid=rec["id"], values=values, tags=(state,))
            shown += 1
        self.status.config(
            text=f"Показано: {shown} из {len(self.records)}   "
                 f"(журнал: {self.schema.name})")

    _STATE_LABEL = {"expired": "просрочен", "unknown": "нет срока"}

    def _display(self, rec, key, state):
        if key == "status" and state in self._STATE_LABEL:
            return self._STATE_LABEL[state]
        return rec.get(key, "")

    @staticmethod
    def _state_of(rec, today):
        if rec.get("status") == STATUS_REVOKED:
            return "revoked"
        d = parse_date(rec.get("valid_until"))
        if d is None:
            return "unknown"
        return "active" if d.date() >= today else "expired"

    def _selected_ids(self):
        return list(self.tree.selection())

    def refresh_filter_sources(self):
        for key, field in self._extra_widgets.items():
            if _EXTRA_FILTERS[key][0] == "combobox":
                current = field.get()
                field.widget.configure(values=[""] + self.journal.distinct(key))
                field.set(current)

    def _save(self, action, *args):
        try:
            self.records = action(*args)
            self.refresh_filter_sources()
            return True
        except FileBusy as exc:
            messagebox.showerror(
                "Файл занят",
                f"«{os.path.basename(exc.path)}» открыт в другой программе.\n"
                "Закройте его и повторите операцию.", parent=self.win)
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось сохранить журнал:\n{exc}",
                                 parent=self.win)
        return False

    def delete_selected(self):
        ids = self._selected_ids()
        if not ids:
            messagebox.showinfo("Выбор", "Выберите записи.", parent=self.win)
            return
        if not messagebox.askyesno(
                "Удаление без следа",
                f"Удалить записи ({len(ids)} шт.) НАВСЕГДА?\n\n"
                "Для отзыва пропуска правильнее «Аннулировать» — запись\n"
                "останется в журнале с отметкой и датой.",
                parent=self.win):
            return
        if self._save(self.journal.delete_ids, ids):
            self.apply_filter()

    def revoke_selected(self):
        ids = self._selected_ids()
        if not ids:
            messagebox.showinfo("Выбор", "Выберите записи.", parent=self.win)
            return
        reason = simpledialog.askstring(
            "Аннулирование", f"Причина аннулирования ({len(ids)} шт.):",
            parent=self.win)
        if reason is None:
            return
        reason = reason.strip() or "не указана"
        if self._save(self.journal.revoke_ids, ids, reason):
            self.apply_filter()
            self._offer_blacklist(ids, reason)

    def _offer_blacklist(self, ids, reason):
        id_set = set(ids)
        records = [r for r in self.records if r.get("id") in id_set]
        if not records:
            return
        word = "запись" if len(records) == 1 else "записи"
        if not messagebox.askyesno(
                "Чёрный список",
                f"Добавить аннулированн{'ую' if len(records) == 1 else 'ые'} "
                f"{word} ({len(records)} шт.) в чёрный список нарушителей?",
                parent=self.win):
            return
        for rec in records:
            plate = rec.get("plate", "")
            fio = rec.get("driver") or rec.get("fio") or ""
            blacklist.add(plate, fio, reason)

    def edit_selected(self):
        ids = self._selected_ids()
        if not ids:
            messagebox.showinfo("Выбор", "Выберите запись.", parent=self.win)
            return
        rec = next((r for r in self.records if r["id"] == ids[0]), None)
        if rec is None:
            return
        EditRecordDialog(self.win, self.theme, self.schema, rec, self._on_edited)

    def _on_edited(self, rec_id, values):
        if self._save(self.journal.update_record, rec_id, values):
            self.apply_filter()
            return True
        return False

    def open_excel(self):
        path = self.schema.xlsx_path
        try:
            rows = [[rec.get(k, "") for k in self.schema.keys] for rec in self.records]
            export_records_to_xlsx(rows, self.schema.cols_def, path, self.schema.name)
        except (FileBusy, PermissionError):
            messagebox.showerror("Файл занят",
                                 "Файл журнала открыт в Excel или другой программе.\n"
                                 "Закройте его и повторите попытку.", parent=self.win)
            return
        except Exception as exc:
            messagebox.showerror("Ошибка", str(exc), parent=self.win)
            return
        try:
            os.startfile(path)  # noqa: Windows only
        except AttributeError:
            messagebox.showinfo("Файл журнала", path, parent=self.win)
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось открыть файл: {exc}",
                                 parent=self.win)


class EditRecordDialog:
    """Модальное окно редактирования записи с поддержкой прокрутки."""

    def __init__(self, parent, theme: Theme, schema, rec, on_save):
        self.rec = rec
        self.on_save = on_save
        th = theme
        self.win = th.toplevel(parent, "Редактирование записи", resizable=(True, True))
        self.win.grab_set()

        w = int(540 * th.scale)
        h = int(min(640 * th.scale, self.win.winfo_screenheight() - 100))
        self.win.geometry(f"{w}x{h}")
        self.win.minsize(int(460 * th.scale), int(380 * th.scale))

        btn_box = tk.Frame(self.win, bg=th.c("ground"))
        btn_box.pack(side="bottom", fill="x", padx=th.sp(4), pady=th.sp(3))
        ttk.Button(btn_box, text="Сохранить изменения", command=self._save,
                   style="Primary.TButton").pack(fill="x")

        _, _, inner = make_scrollable(self.win, th.c("ground"))
        pad = tk.Frame(inner, bg=th.c("ground"))
        pad.pack(fill="both", expand=True, padx=th.sp(4), pady=th.sp(3))

        self.entries = {}
        for f in schema.fields:
            if f.key == "id":
                continue
            entry = Field(pad, th, f.title, width=38)
            entry.pack(fill="x", pady=(0, th.sp(2)))
            entry.set(rec.get(f.key, ""))
            self.entries[f.key] = entry

        tk.Label(pad, text=f"ID записи: {rec.get('id','')}", bg=th.c("ground"),
                 fg=th.c("ink_faint"), font=th.font("caption")).pack(
            anchor="w", pady=(th.sp(2), th.sp(2)))

    def _save(self):
        values = {k: e.get().strip() for k, e in self.entries.items()}
        if self.on_save(self.rec["id"], values):
            self.win.destroy()