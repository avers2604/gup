"""Окно «Незавершённые выдачи»: обработка нескольких выбранных операций."""
import os

import pytest

from getpass_core import issuance

tkinter = pytest.importorskip("tkinter")

needs_display = pytest.mark.skipif(os.name != "nt" and not os.environ.get("DISPLAY"),
                                   reason="нужен X-сервер")


@needs_display
class TestOperationsDialogPartialFailure:
    @pytest.fixture
    def dialog(self, data_dir, monkeypatch):
        from getpass_core.storage import PASS_JOURNAL
        from getpass_ui.operations import _OperationsDialog
        from getpass_ui.theme import Theme
        root = tkinter.Tk()
        th = Theme(root, "light")
        self.ok_id = issuance.prepare(PASS_JOURNAL, [{"num": "1", "plate": "А1АА78"}], "printer")
        self.fail_id = issuance.prepare(PASS_JOURNAL, [{"num": "2", "plate": "А2АА78"}], "printer")
        dlg = _OperationsDialog(root, th)
        root.update()
        yield dlg
        root.destroy()

    def test_confirm_continues_past_failure_and_refreshes(self, dialog, monkeypatch):
        from tkinter import messagebox
        monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: True)
        errors = []
        monkeypatch.setattr(messagebox, "showerror",
                            lambda title, text, **k: errors.append((title, text)))

        real_confirm = issuance.confirm

        def flaky_confirm(journal, operation_id):
            if operation_id == self.fail_id:
                raise ValueError("подтверждение недоступно")
            return real_confirm(journal, operation_id)

        monkeypatch.setattr(issuance, "confirm", flaky_confirm)
        dialog.tree.selection_set(self.ok_id, self.fail_id)

        dialog.confirm()

        # Успешная операция обработана несмотря на то, что вторая упала...
        assert self.ok_id not in dialog.jobs
        # ...а провалившаяся всё ещё видна как незавершённая, а не потеряна.
        assert self.fail_id in dialog.jobs
        assert errors  # оператор узнал об ошибке
