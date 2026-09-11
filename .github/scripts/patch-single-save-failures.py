from pathlib import Path


def replace_once(path, old, new):
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one match, found {count}")
    file_path.write_text(text.replace(old, new), encoding="utf-8")


replace_once(
    "getpass_ui/app.py",
    '''        try:\n            self._issuance_id = issuance.prepare(PASS_JOURNAL, records, path)\n''',
    '''        operation_id = None\n        try:\n            operation_id = issuance.prepare(PASS_JOURNAL, records, path)\n            self._issuance_id = operation_id\n''',
)
replace_once(
    "getpass_ui/app.py",
    '''        except Exception as exc:\n            messagebox.showerror("Ошибка", f"Не удалось сохранить файл:\\n{exc}")\n            return\n        if not self._finish_pass(records, next_num):\n''',
    '''        except Exception as exc:\n            recovery_note = ""\n            if operation_id is not None:\n                try:\n                    issuance.cancel(PASS_JOURNAL, operation_id)\n                    self._issuance_id = None\n                except Exception as cancel_exc:\n                    recovery_note = (\n                        "\\n\\nОперация осталась в «Незавершённых выдачах»: "\n                        f"{cancel_exc}"\n                    )\n            messagebox.showerror(\n                "Ошибка", f"Не удалось сохранить файл:\\n{exc}{recovery_note}"\n            )\n            return\n        if not self._finish_pass(records, next_num):\n''',
)
replace_once(
    "getpass_ui/badge_tab.py",
    '''        try:\n            self._issuance_id = issuance.prepare(BADGE_JOURNAL, [data], path)\n            printing.save_document(document, path)\n        except Exception as exc:\n            messagebox.showerror("Ошибка", f"Не удалось сохранить файл:\\n{exc}")\n            return\n''',
    '''        operation_id = None\n        try:\n            operation_id = issuance.prepare(BADGE_JOURNAL, [data], path)\n            self._issuance_id = operation_id\n            printing.save_document(document, path)\n        except Exception as exc:\n            recovery_note = ""\n            if operation_id is not None:\n                try:\n                    issuance.cancel(BADGE_JOURNAL, operation_id)\n                    self._issuance_id = None\n                except Exception as cancel_exc:\n                    recovery_note = (\n                        "\\n\\nОперация осталась в «Незавершённых выдачах»: "\n                        f"{cancel_exc}"\n                    )\n            messagebox.showerror(\n                "Ошибка", f"Не удалось сохранить файл:\\n{exc}{recovery_note}"\n            )\n            return\n''',
)
