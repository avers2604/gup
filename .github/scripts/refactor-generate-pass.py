from pathlib import Path

path = Path("getpass_ui/app.py")
text = path.read_text(encoding="utf-8")

marker = "    def generate_pass(self):\n"
helpers = '''    def _save_pass_file(self, document, back_document, path):\n        is_pdf = os.path.splitext(path)[1].lower() == ".pdf"\n        if back_document is not None and is_pdf:\n            printing.save_pdf_pages([document, back_document], path)\n            return\n        printing.save_document(document, path)\n        if back_document is not None:\n            messagebox.showinfo(\n                "Оборот не сохранён",\n                "Оборотная сторона поддерживается только при сохранении в PDF.\\n"\n                "Сохранена только лицевая сторона.",\n            )\n\n    def _report_pass_save_failure(self, operation_id, exc):\n        recovery_note = ""\n        if operation_id is not None:\n            try:\n                issuance.cancel(PASS_JOURNAL, operation_id)\n                self._issuance_id = None\n            except Exception as cancel_exc:\n                recovery_note = (\n                    "\\n\\nОперация осталась в «Незавершённых выдачах»: "\n                    f"{cancel_exc}"\n                )\n        messagebox.showerror(\n            "Ошибка", f"Не удалось сохранить файл:\\n{exc}{recovery_note}"\n        )\n\n    def generate_pass(self):\n'''
if text.count(marker) != 1:
    raise SystemExit(f"generate_pass marker count: {text.count(marker)}")
text = text.replace(marker, helpers, 1)

old = '''        is_pdf = os.path.splitext(path)[1].lower() == ".pdf"\n        operation_id = None\n        try:\n            operation_id = issuance.prepare(PASS_JOURNAL, records, path)\n            self._issuance_id = operation_id\n            if back_document is not None and is_pdf:\n                printing.save_pdf_pages([document, back_document], path)\n            else:\n                printing.save_document(document, path)\n                if back_document is not None:\n                    messagebox.showinfo(\n                        "Оборот не сохранён",\n                        "Оборотная сторона поддерживается только при сохранении в PDF.\\n"\n                        "Сохранена только лицевая сторона.")\n        except Exception as exc:\n            recovery_note = ""\n            if operation_id is not None:\n                try:\n                    issuance.cancel(PASS_JOURNAL, operation_id)\n                    self._issuance_id = None\n                except Exception as cancel_exc:\n                    recovery_note = (\n                        "\\n\\nОперация осталась в «Незавершённых выдачах»: "\n                        f"{cancel_exc}"\n                    )\n            messagebox.showerror(\n                "Ошибка", f"Не удалось сохранить файл:\\n{exc}{recovery_note}"\n            )\n            return\n'''
new = '''        operation_id = None\n        try:\n            operation_id = issuance.prepare(PASS_JOURNAL, records, path)\n            self._issuance_id = operation_id\n            self._save_pass_file(document, back_document, path)\n        except Exception as exc:\n            self._report_pass_save_failure(operation_id, exc)\n            return\n'''
if text.count(old) != 1:
    raise SystemExit(f"generate_pass body match count: {text.count(old)}")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
