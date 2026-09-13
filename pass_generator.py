"""СПб ГУП «Горэлектротранс» — production entry point for GET-Passes 2.0.

The default application is PySide6. Temporary Tkinter rollback remains in
``legacy_pass_generator.py`` until physical workstation/printer acceptance is
complete.
"""
from __future__ import annotations

import os
import sys
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


def _install_crash_handler() -> None:
    from getpass_core import config

    def handler(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        message = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        config.write_crash_log(message)
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            if QApplication.instance() is not None:
                QMessageBox.critical(
                    None,
                    "Критическая ошибка",
                    f"Ошибка:\n{exc_value}\n\nПодробности в файле:\n{config.CRASH_LOG_FILE}",
                )
        except Exception:
            pass

    sys.excepthook = handler


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    if "--self-test" in args:
        from getpass_qt.app import main as qt_main

        return qt_main(args)

    _install_crash_handler()
    from getpass_core import config
    from getpass_core.instance import single_instance
    from getpass_qt.app import main as qt_main

    with single_instance(config.DATA_DIR):
        return qt_main(args)


if __name__ == "__main__":
    sys.exit(main())
