"""Окно журнала. Одно на оба журнала — раньше это были две копии по 89 строк."""
from __future__ import annotations

import os
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, simpledialog, ttk

from getpass_core.domain import parse_date
from getpass_core.storage import STATUS_REVOKED, FileBusy

from .widgets import F, styled_button


def open_journal_window(parent, journal, title):
    JournalWindow(parent, journal, title)


class JournalWindow:
    def __init__(self, parent, journal, title):
        self.journal = journal
        self.schema = journal.schema
        self.records = journal.read()

        self.win = tk.Toplevel(parent)
        self.win.title(title)
        self.win.geometry("1250x640")
        self.win.minsize(960, 460)
        self.win.transient(parent)

        self._build_filters()
        self._build_tree()
        self._build_buttons()
        self.apply_filter()

    # ------------------------------------------------------ разметка

    def _build_filters(self):
        bar = ttk.Frame(self.win, padding="10")
        bar.pack(fill="x")
        ttk.Label(bar, text="🔍 Поиск:").pack(side="left", padx=(0, 5))
        self.search_var = tk.StringVar()
        ttk.Entry(bar, textvariable=self.search_var, width=30).pack(side="left")
        self.filter_var = tk.StringVar(value="active")
        for text, value in (("Все", "all"), ("Действующие", "active"),
                            ("Просроченные", "expired"), ("Аннулированные", "revoked"),
                            ("Без срока", "unknown")):
            ttk.Radiobutton(bar, text=text, variable=self.filter_var,
                            value=value).pack(side="left", padx=5)
        self.search_var.trace_add("write", self.apply_filter)
        self.filter_var.trace_add("write", self.apply_filter)

    def _build_tree(self):
        frame = ttk.Frame(self.win, padding="10")
        frame.pack(fill="both", expand=True)
        self.visible_fields = [f for f in self.schema.fields if f.tree_width > 0]
        columns = [f.key for f in self.visible_fields]
        self.tree = ttk.Treeview(frame, columns=columns, show="headings",
                                 selectmode="extended")
        for f in self.visible_fields:
            self.tree.heading(f.key, text=f.title,
                              command=lambda k=f.key: self._sort_by(k))
            self.tree.column(f.key, width=f.tree_width, anchor=f.anchor)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.tag_configure("revoked", foreground="#9AA5B1")
        self.tree.tag_configure("expired", foreground="#C62828")
        self.tree.tag_configure("unknown", background="#FFF4E5")
        self.tree.bind("<Double-1>", lambda e: self.edit_selected())

    def _build_buttons(self):
        bar = ttk.Frame(self.win, padding="10")
        bar.pack(fill="x")
        self.status = ttk.Label(bar, text="", font=F(9, True))
        self.status.pack(side="left")
        styled_button(bar, "✏️ Изменить", self.edit_selected, "#1976D2",
                      padx=12, pady=6).pack(side="left", padx=(14, 6))
        styled_button(bar, "📄 Открыть в Excel", self.open_excel, "#2E7D32",
                      padx=12, pady=6).pack(side="right")
        styled_button(bar, "❌ Удалить", self.delete_selected, "#C62828",
                      padx=12, pady=6).pack(side="right", padx=(0, 6))
        styled_button(bar, "🚫 Аннулировать", self.revoke_selected, "#EF6C00",
                      padx=12, pady=6).pack(side="right", padx=(0, 6))

    # ------------------------------------------------------- выборка

    def _sort_by(self, key):
        self.records.sort(key=lambda r: (r.get(key) or "").lower())
        self.apply_filter()

    def apply_filter(self, *_args):
        query = self.search_var.get().lower().strip()
        mode = self.filter_var.get()
        today = datetime.now().date()
        self.tree.delete(*self.tree.get_children())
        shown = 0
        for rec in self.records:
            if query and not any(query in str(v).lower() for v in rec.values()):
                continue
            state = self._state_of(rec, today)
            if mode != "all" and state != mode:
                continue
            values = [rec.get(f.key, "") for f in self.visible_fields]
            self.tree.insert("", "end", iid=rec["id"], values=values,
                             tags=(state,) if state != "active" else ())
            shown += 1
        self.status.config(
            text=f"Показано: {shown} из {len(self.records)}   "
                 f"(журнал: {self.schema.name})")

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

    # ------------------------------------------------------ действия

    def _save(self, action, *args):
        """Выполнить операцию журнала, показав внятную ошибку при занятом файле."""
        try:
            self.records = action(*args)
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
        if self._save(self.journal.revoke_ids, ids, reason.strip() or "не указана"):
            self.apply_filter()

    def edit_selected(self):
        ids = self._selected_ids()
        if not ids:
            messagebox.showinfo("Выбор", "Выберите запись.", parent=self.win)
            return
        rec = next((r for r in self.records if r["id"] == ids[0]), None)
        if rec is None:
            return
        EditRecordDialog(self.win, self.schema, rec, self._on_edited)

    def _on_edited(self, rec_id, values):
        if self._save(self.journal.update_record, rec_id, values):
            self.apply_filter()
            return True
        return False

    def open_excel(self):
        path = self.schema.xlsx_path
        if not os.path.exists(path):
            try:
                self.journal.write(self.records)
            except Exception as exc:
                messagebox.showerror("Ошибка", str(exc), parent=self.win)
                return
        try:
            os.startfile(path)  # noqa: attribute defined only on Windows
        except AttributeError:
            messagebox.showinfo("Файл журнала", path, parent=self.win)
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось открыть файл: {exc}",
                                 parent=self.win)


class EditRecordDialog:
    def __init__(self, parent, schema, rec, on_save):
        self.rec = rec
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Редактирование записи")
        self.win.geometry("620x520")
        self.win.transient(parent)
        self.win.grab_set()
        frame = ttk.Frame(self.win, padding=20)
        frame.pack(fill="both", expand=True)
        self.entries = {}
        row = 0
        for f in schema.fields:
            if f.key == "id":
                continue
            ttk.Label(frame, text=f.title, font=F(9, True)).grid(
                row=row, column=0, sticky="w", pady=4)
            entry = ttk.Entry(frame, width=44, font=F(10))
            entry.grid(row=row, column=1, pady=4, sticky="w")
            entry.insert(0, rec.get(f.key, ""))
            self.entries[f.key] = entry
            row += 1
        ttk.Label(frame, text=f"ID записи: {rec.get('id','')}",
                  font=F(8, italic=True), foreground="#829AB1").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(10, 0))
        styled_button(frame, "💾 Сохранить изменения", self._save, "#2E7D32",
                      font=F(10, True), pady=6).grid(
            row=row + 1, column=0, columnspan=2, pady=18, sticky="ew")

    def _save(self):
        values = {k: e.get().strip() for k, e in self.entries.items()}
        if self.on_save(self.rec["id"], values):
            self.win.destroy()
