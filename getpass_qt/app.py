from __future__ import annotations

import argparse
import os

from PIL import Image
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from getpass_app.services.employee_badge_service import EmployeeBadgeService
from getpass_app.services.settings_service import SettingsService
from getpass_app.services.vehicle_pass_service import VehiclePassService
from getpass_qt.main_window import MainWindow
from getpass_qt.theme.manager import ThemeManager
from getpass_qt.viewmodels.employee_badge_viewmodel import EmployeeBadgeViewModel
from getpass_qt.viewmodels.vehicle_pass_viewmodel import VehiclePassViewModel


class _SelfTestBadgeJournal:
    @staticmethod
    def distinct(column):
        return ("ВОДИТЕЛЬ",) if column == "role" else ()

    @staticmethod
    def find_duplicates(_tab_num):
        return ()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="GET-Passes Qt Preview")
    parser.add_argument("--self-test", action="store_true")
    return parser


def _vehicle_viewmodel(*, self_test: bool) -> VehiclePassViewModel:
    if self_test:
        service = VehiclePassService(
            lookup=lambda plate: None,
            zone_values=lambda: (),
            brand_values=lambda: (),
            printer_values=lambda: ("По умолчанию",),
        )
    else:
        service = VehiclePassService()
    return VehiclePassViewModel(service)


def _employee_badge_viewmodel(*, self_test: bool) -> EmployeeBadgeViewModel:
    if self_test:
        service = EmployeeBadgeService(
            journal=_SelfTestBadgeJournal(),
            blacklist_lookup=lambda **_kwargs: (),
            printer_values=lambda: ("По умолчанию",),
            render=lambda _data: Image.new("RGB", (1016, 638), "white"),
            prepare=lambda *_args: "self-test",
            confirm=lambda *_args: None,
            cancel=lambda *_args: None,
            save_document=lambda *_args: None,
            print_one=lambda *_args: (True, ""),
            file_exists=lambda _path: True,
        )
    else:
        service = EmployeeBadgeService()
    return EmployeeBadgeViewModel(service)


def _wait_for_preview_refresh(_window, app) -> None:
    loop = QEventLoop()
    QTimer.singleShot(250, loop.quit)
    loop.exec()
    app.processEvents()


def _exercise_self_test(window, app) -> None:
    assert window.active_route == "dashboard"
    assert window.stack.count() == 8

    window.sidebar.request_route("vehicle")
    app.processEvents()
    assert window.active_route == "vehicle"

    preview = window.vehicle_page.preview
    preview.set_pil_image(None)
    assert not preview.has_image

    plate = window.vehicle_page.pass_fields["first"]["plate"]
    plate.setText("А111АА78")
    app.processEvents()
    assert not preview.has_image

    _wait_for_preview_refresh(window, app)
    assert preview.has_image

    window.sidebar.request_route("employee")
    app.processEvents()
    assert window.active_route == "employee"

    badge_preview = window.employee_page.preview
    badge_preview.set_pil_image(None)
    assert not badge_preview.has_image

    window.employee_page.surname_edit.setText("ИВАНОВ")
    app.processEvents()
    assert not badge_preview.has_image

    _wait_for_preview_refresh(window, app)
    assert badge_preview.has_image


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.self_test:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    app = QApplication.instance() or QApplication(["GET-Passes Qt Preview"])
    if args.self_test:
        settings = SettingsService(
            load=lambda: {"theme": "light"},
            save=lambda values: True,
        )
    else:
        settings = SettingsService()

    theme = ThemeManager(app, settings)
    theme.load()
    window = MainWindow(
        theme_manager=theme,
        vehicle_viewmodel=_vehicle_viewmodel(self_test=args.self_test),
        employee_badge_viewmodel=_employee_badge_viewmodel(
            self_test=args.self_test
        ),
    )

    if args.self_test:
        window.show()
        app.processEvents()
        _exercise_self_test(window, app)
        window.close()
        app.processEvents()
        return 0

    window.show()
    return app.exec()
