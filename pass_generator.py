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
    _install_crash_handler()
    from getpass_ui.app import App
    App().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
