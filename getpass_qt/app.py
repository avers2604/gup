from __future__ import annotations

import argparse
import os

from PIL import Image
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from getpass_app.models.journal import JournalField, JournalSnapshot
from getpass_app.services.batch_service import BatchService
from getpass_app.services.employee_badge_service import EmployeeBadgeService
from getpass_app.services.journal_service import JournalService
from getpass_app.services.operations_service import OperationsService
from getpass_app.services.settings_service import SettingsService
from getpass_app.services.vehicle_pass_service import VehiclePassService
from getpass_qt.main_window import MainWindow
from getpass_qt.theme.manager import ThemeManager
from getpass_qt.viewmodels.batch_viewmodel import BatchViewModel
from getpass_qt.viewmodels.employee_badge_viewmodel import EmployeeBadgeViewModel
from getpass_qt.viewmodels.journal_viewmodel import JournalViewModel
from getpass_qt.viewmodels.operations_viewmodel import OperationsViewModel
from getpass_qt.viewmodels.vehicle_pass_viewmodel import VehiclePassViewModel


class _SelfTestBadgeJournal:
    @staticmethod
    def distinct(column):
        return ("ВОДИТЕЛЬ",) if column == "role" else ()

    @staticmethod
    def find_duplicates(_tab_num):
        return ()


class _SelfTestJournalService:
    @staticmethod
    def journal_keys():
        return ("pass", "badge")

    @staticmethod
    def snapshot(journal_key, filters, **kwargs):
        return JournalSnapshot(
            journal_key=journal_key,
            journal_name="Self-test journal",
            fields=(JournalField("status", "Статус", 100),),
            rows=(),
            total_records=0,
            filtered_records=0,
            page=0,
            page_size=kwargs.get("page_size", 100),
            page_count=1,
        )

    @staticmethod
    def distinct(journal_key, key):
        return ()

    @staticmethod
    def update_record(*_args):
        raise AssertionError("self-test must not update journal data")

    @staticmethod
    def revoke(*_args):
        raise AssertionError("self-test must not revoke journal data")

    @staticmethod
    def history(*_args):
        return ()

    @staticmethod
    def export(*_args):
        raise AssertionError("self-test must not export journal data")

    @staticmethod
    def add_revoked_to_blacklist(*_args):
        raise AssertionError("self-test must not edit blacklist data")


class _SelfTestOperationsService:
    @staticmethod
    def pending():
        return ()

    @staticmethod
    def confirm(_ids):
        raise AssertionError("self-test must not confirm operations")

    @staticmethod
    def cancel(_ids):
        raise AssertionError("self-test must not cancel operations")


class _SelfTestBatchService:
    @staticmethod
    def _unexpected():
        raise AssertionError("self-test must not access batch files or output")

    def read_csv(self, _path):
        return self._unexpected()

    def parse_pass_rows(self, _rows, _defaults):
        return self._unexpected()

    def parse_badge_rows(self, _rows, _folder, _defaults):
        return self._unexpected()

    def review(self, _kind, _items):
        return self._unexpected()

    def export_template(self, _kind, _path):
        return self._unexpected()

    def generate_pdf(self, _kind, _items, _path, *, cancelled, progress):
        return self._unexpected()


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


def _batch_viewmodel(*, self_test: bool) -> BatchViewModel:
    service = _SelfTestBatchService() if self_test else BatchService()
    return BatchViewModel(service)


def _journal_viewmodel(*, self_test: bool) -> JournalViewModel:
    service = _SelfTestJournalService() if self_test else JournalService()
    return JournalViewModel(service)


def _operations_viewmodel(*, self_test: bool) -> OperationsViewModel:
    service = _SelfTestOperationsService() if self_test else OperationsService()
    return OperationsViewModel(service)


def _wait_for_preview_refresh(_window, app) -> None:
    loop = QEventLoop()
    QTimer.singleShot(250, loop.quit)
    loop.exec()
    app.processEvents()


def _exercise_self_test(window, app) -> None:
    assert window.active_route == "dashboard"
    assert window.stack.count() == 9

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

    window.sidebar.request_route("batch")
    app.processEvents()
    assert window.active_route == "batch"

    window.sidebar.request_route("journals")
    app.processEvents()
    assert window.active_route == "journals"

    window.sidebar.request_route("operations")
    app.processEvents()
    assert window.active_route == "operations"


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
        batch_viewmodel=_batch_viewmodel(self_test=args.self_test),
        journal_viewmodel=_journal_viewmodel(self_test=args.self_test),
        operations_viewmodel=_operations_viewmodel(self_test=args.self_test),
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
