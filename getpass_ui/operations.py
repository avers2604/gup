"""Recovery and inspection of durable issuance operations."""
import os
from tkinter import messagebox, ttk

from getpass_core import issuance
from getpass_core.storage import BADGE_JOURNAL, PASS_JOURNAL

_SUPPORTED_DOCUMENT_EXTENSIONS = (".pdf", ".jpg", ".png")


class _OperationsDialog:
    def __init__(self, parent, theme):
        self.win = theme.toplevel(parent, "Незавершённые выдачи")
        self.win.geometry("1120x550")
        ttk.Label(
            self.win,
            text=(
                "Здесь показаны операции, для которых выдача ещё не подтверждена. "
                "Подтвердите только фактически выданный документ или отмените операцию."
            ),
        ).pack(pady=12)
        self.tree = ttk.Treeview(
            self.win,
            columns=("created", "journal", "destination", "document"),
            show="headings",
        )
        self._configure_tree()
        self.tree.pack(fill="both", expand=True, padx=12)
        self.jobs = {}
        self._build_buttons()
        self.refresh()

    def _configure_tree(self):
        columns = (
            ("created", "Создана", 210),
            ("journal", "Журнал", 190),
            ("destination", "Файл / принтер", 430),
            ("document", "Документ", 170),
        )
        for key, label, width in columns:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width)

    def _build_buttons(self):
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=12)
        ttk.Button(bar, text="Обновить", command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Открыть документ", command=self.open_file).pack(
            side="left", padx=8
        )
        ttk.Button(bar, text="Отменить операцию", command=self.cancel).pack(
            side="left"
        )
        ttk.Button(bar, text="Подтвердить выдачу", command=self.confirm).pack(side="right")

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        self.jobs.clear()
        for journal in (PASS_JOURNAL, BADGE_JOURNAL):
            self._load_journal(journal)

    def _load_journal(self, journal):
        for job in issuance.pending(journal):
            self.jobs[job["id"]] = (journal, job)
            destination = job["destination"]
            self.tree.insert(
                "",
                "end",
                iid=job["id"],
                values=(
                    job["created_at"],
                    journal.schema.name,
                    destination,
                    self._document_status(destination),
                ),
            )

    def confirm(self):
        selected = self.tree.selection()
        if not selected:
            return
        if not messagebox.askyesno(
            "Подтвердить выдачу",
            "Документы действительно выданы? Записать их в журнал?",
            parent=self.win,
        ):
            return
        try:
            for key in selected:
                issuance.confirm(self.jobs[key][0], key)
            self.refresh()
        except Exception as exc:
            messagebox.showerror("Не удалось подтвердить", str(exc), parent=self.win)

    def cancel(self):
        selected = self.tree.selection()
        if not selected:
            return
        if not messagebox.askyesno(
            "Отменить операцию",
            "Отменённые операции нельзя будет подтвердить позже. Продолжить?",
            parent=self.win,
        ):
            return
        try:
            for key in selected:
                issuance.cancel(self.jobs[key][0], key)
            self.refresh()
        except Exception as exc:
            messagebox.showerror("Не удалось отменить", str(exc), parent=self.win)

    def open_file(self):
        selected = self.tree.selection()
        if not selected:
            return
        path = self.jobs[selected[0]][1]["destination"]
        if not self._is_document_path(path):
            messagebox.showinfo(
                "Прямая печать",
                "Эта операция связана с принтером и не содержит сохранённого файла.",
                parent=self.win,
            )
            return
        if not os.path.isfile(path):
            messagebox.showwarning(
                "Файл не найден",
                "Сохранённый документ отсутствует. Проверьте выдачу и отмените операцию, "
                "если документ фактически не был выдан.",
                parent=self.win,
            )
            return
        try:
            os.startfile(path)  # noqa: Windows only
        except Exception as exc:
            messagebox.showerror(
                "Не удалось открыть документ",
                str(exc),
                parent=self.win,
            )

    @staticmethod
    def _is_document_path(path):
        return bool(path) and path.lower().endswith(_SUPPORTED_DOCUMENT_EXTENSIONS)

    @classmethod
    def _document_status(cls, path):
        if not cls._is_document_path(path):
            return "Прямая печать"
        return "Файл готов" if os.path.isfile(path) else "Файл не найден"


def open_operations(parent, theme):
    _OperationsDialog(parent, theme)
