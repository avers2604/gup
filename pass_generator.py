"""СПб ГУП «Горэлектротранс» — система выпуска пропусков на ТС и бейджей.

Точка входа. Прикладная логика вынесена в пакеты:
    getpass_core/  — предметная логика, хранилище, отрисовка, печать
    getpass_ui/    — интерфейс Tkinter

Запуск:  python pass_generator.py
"""
from __future__ import annotations

import os
import sys
import traceback

# запуск возможен из ярлыка с произвольным рабочим каталогом и из сборки
# PyInstaller — гарантируем, что пакеты рядом со скриптом видны
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


def _install_crash_handler():
    from getpass_core import config

    def handler(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        message = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        config.write_crash_log(message)
        try:
            from tkinter import messagebox
            messagebox.showerror(
                "Критическая ошибка",
                f"Ошибка:\n{exc_value}\n\nПодробности в файле:\n{config.CRASH_LOG_FILE}")
        except Exception:
            pass

    sys.excepthook = handler


def main() -> int:
    if "--self-test" in sys.argv:
        import tempfile
        with tempfile.TemporaryDirectory(prefix="get-smoke-") as temporary:
            os.environ["GET_PASSES_DATA_DIR"] = temporary
            from getpass_ui.app import App
            from getpass_core.render import render_pass
            from getpass_core.printing import save_document
            from getpass_core.storage import PASS_JOURNAL
            App._load_printers = lambda self: self._printer_result.put(["По умолчанию"])
            App._startup_checks = lambda self: None
            app = App()
            try:
                app.root.withdraw()
                app.root.update_idletasks()
                image = render_pass({"num": "TEST", "plate": "А111АА78"}, {})
                save_document(image, os.path.join(temporary, "smoke.pdf"))
                PASS_JOURNAL.append_many([{"num": "TEST"}])
                assert PASS_JOURNAL.read()[0]["num"] == "TEST"
            finally:
                app.root.destroy()
        return 0
    _install_crash_handler()
    # объявить DPI-осведомлённость нужно ДО создания окна Tk, иначе Windows
    # отрисует интерфейс в 96 dpi и растянет картинку — отсюда «мыло»
    from getpass_core.dpi import enable_dpi_awareness
    enable_dpi_awareness()
    from getpass_ui.app import App
    from getpass_core import config
    from getpass_core.instance import single_instance
    with single_instance(config.DATA_DIR):
        App().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
