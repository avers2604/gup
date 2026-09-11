from pathlib import Path

path = Path("getpass_ui/app.py")
text = path.read_text(encoding="utf-8")
start_marker = "    def _send_pass_to_printer(self, document, back_document, printer):\n"
end_marker = "    def _confirm_flip_for_back_side(self) -> bool:\n"
if text.count(start_marker) != 1 or text.count(end_marker) != 1:
    raise RuntimeError("app helper boundaries are not unique")
start = text.index(start_marker)
end = text.index(end_marker, start)
replacement = '''    def _send_pass_to_printer(self, document, back_document, printer):
        if back_document is not None:
            return run_task(
                self.root,
                lambda ask: printing.print_pass_two_sided(
                    document, back_document, printer, confirm_flip=ask
                ),
                "Двусторонняя печать",
                confirm=self._confirm_flip_for_back_side,
            )
        return run_task(
            self.root,
            lambda: printing.send_image_to_printer(document, printer),
            "Печать",
        )

    @staticmethod
    def _open_manual_print_copy(document, back_document, prefix):
        temp_pdf = os.path.join(config.DATA_DIR, f"_print_{prefix}.pdf")
        try:
            if back_document is not None:
                printing.save_pdf_pages([document, back_document], temp_pdf)
            else:
                printing.save_document(document, temp_pdf)
            os.startfile(temp_pdf)  # noqa: Windows only
            return True
        except Exception:
            return False

    @staticmethod
    def _confirm_manual_issuance(err, opened):
        opened_note = "Документ открыт — напечатайте вручную (Ctrl+P).\\n\\n" if opened else ""
        return messagebox.askyesno(
            "Принтер не ответил",
            f"Не удалось напечатать напрямую.\\n{err or ''}\\n\\n"
            + opened_note
            + "Считать пропуск выданным и записать в журнал?",
        )

    def direct_print_pass(self):
        built = self.build_documents()
        if not built:
            return
        document, back_document, prefix, records, next_num = built
        printer = self.printer_var.get()
        try:
            self._issuance_id = issuance.prepare(PASS_JOURNAL, records, printer)
        except Exception as exc:
            messagebox.showerror("Выдача не начата", str(exc))
            return
        ok, err = self._send_pass_to_printer(document, back_document, printer)
        if ok:
            if not self._finish_pass(records, next_num):
                return
            messagebox.showinfo("Печать", "Документ успешно отправлен на принтер!")
            return
        opened = self._open_manual_print_copy(document, back_document, prefix)
        if self._confirm_manual_issuance(err, opened):
            self._finish_pass(records, next_num)

'''
path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
