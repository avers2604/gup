"""Recovery and inspection of durable issuance operations."""
import os
from tkinter import messagebox, ttk

from getpass_core import issuance
from getpass_core.storage import BADGE_JOURNAL, PASS_JOURNAL


class _OperationsDialog:
    def __init__(self, parent, theme):
        self.win = theme.toplevel(parent, "Незавершённые выдачи")
        self.win.geometry("1000x550")
        ttk.Label(
            self.win,
            text="Операции сохраняются до печати. Подтверждайте выдачу после проверки документа.",
        ).pack(pady=12)
        self.tree = ttk.Treeview(
            self.win,
            columns=("created", "journal", "destination"),
            show="headings",
        )
        self._configure_tree()
        self.tree.pack(fill="both", expand=True, padx=12)
        self.jobs = {}
        self._build_buttons()
        self.refresh()

    def _configure_tree(self):
        columns = (
            ("created", "Создана"),
            ("journal", "Журнал"),
            ("destination", "Файл / принтер"),
        )
        for key, label in columns:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=250)

    def _build_buttons(self):
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=12)
        ttk.Button(bar, text="Обновить", command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Открыть документ", command=self.open_file).pack(
            side="left", padx=8
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
            self.tree.insert(
                "",
                "end",
                iid=job["id"],
                values=(job["created_at"], journal.schema.name, job["destination"]),
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

    def open_file(self):
        selected = self.tree.selection()
        if not selected:
            return
        path = self.jobs[selected[0]][1]["destination"]
        if self._can_open(path):
            os.startfile(path)
            return
        messagebox.showinfo(
            "Файл недоступен",
            "Документ не сохранён. Повторите подготовку по данным операции.",
            parent=self.win,
        )

    @staticmethod
    def _can_open(path):
        return os.path.isfile(path) and path.lower().endswith((".pdf", ".jpg", ".png"))


def open_operations(parent, theme):
    _OperationsDialog(parent, theme)
