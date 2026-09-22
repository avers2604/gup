from PySide6.QtCore import Qt

from getpass_app.models.blacklist import BlacklistEntry
from getpass_app.models.preferences import OperatorDefaults
from getpass_qt.viewmodels.blacklist_viewmodel import BlacklistViewModel
from getpass_qt.viewmodels.settings_viewmodel import SettingsViewModel
from getpass_qt.views.settings import SettingsPage


class FakeSettingsService:
    def __init__(self):
        self.saved = []

    def save_operator_defaults(self, defaults):
        self.saved.append(defaults)
        return True


class FakeBlacklistService:
    def __init__(self):
        self.entries = [
            BlacklistEntry(
                id="abc123",
                plate="А111АА78",
                fio="ИВАНОВ И.И.",
                incident="Нарушение режима",
                created_at="13.09.2026 12:30",
            )
        ]
        self.added = []
        self.removed = []

    def list_entries(self):
        return tuple(self.entries)

    def add_entry(self, *, plate, fio, incident):
        self.added.append((plate, fio, incident))
        entry = BlacklistEntry(
            id="new456",
            plate=plate,
            fio=fio,
            incident=incident,
            created_at="13.09.2026 13:00",
        )
        self.entries.append(entry)
        return entry

    def remove_entry(self, entry_id):
        self.removed.append(entry_id)
        self.entries = [entry for entry in self.entries if entry.id != entry_id]


def make_page(qtbot):
    settings_service = FakeSettingsService()
    blacklist_service = FakeBlacklistService()
    settings_vm = SettingsViewModel(
        settings_service,
        defaults=OperatorDefaults(territory="Площадка 1"),
    )
    blacklist_vm = BlacklistViewModel(blacklist_service)
    page = SettingsPage(
        settings_vm,
        blacklist_vm,
        confirm_remove=lambda _entry: True,
    )
    qtbot.addWidget(page)
    return page, settings_service, blacklist_service, settings_vm, blacklist_vm


def test_settings_page_has_parameters_and_blacklist_tabs(qtbot):
    page, *_ = make_page(qtbot)

    assert page.tabs.count() == 2
    assert page.tabs.tabText(0) == "Параметры"
    assert page.tabs.tabText(1) == "Черный список"
    assert page.blacklist_table.model().rowCount() == 1


def test_settings_page_edits_and_saves_operator_defaults(qtbot):
    page, service, _, vm, _ = make_page(qtbot)

    page.territory_edit.setText("Площадка 2")
    qtbot.mouseClick(page.save_button, Qt.MouseButton.LeftButton)

    assert vm.defaults.territory == "Площадка 2"
    assert service.saved == [vm.defaults]
    assert "сохран" in page.status_label.text().lower()


def test_settings_page_adds_blacklist_entry_and_refreshes_table(qtbot):
    page, _, service, _, _ = make_page(qtbot)

    page.plate_edit.setText("В222ВВ78")
    page.fio_edit.setText("ПЕТРОВ П.П.")
    page.incident_edit.setText("Новый инцидент")
    qtbot.mouseClick(page.add_blacklist_button, Qt.MouseButton.LeftButton)

    assert service.added == [("В222ВВ78", "ПЕТРОВ П.П.", "Новый инцидент")]
    assert page.blacklist_table.model().rowCount() == 2
    assert page.plate_edit.text() == ""
    assert page.incident_edit.text() == ""


def test_settings_page_removes_selected_blacklist_entry(qtbot):
    page, _, service, _, _ = make_page(qtbot)

    page.blacklist_table.selectRow(0)
    qtbot.mouseClick(page.remove_blacklist_button, Qt.MouseButton.LeftButton)

    assert service.removed == ["abc123"]
    assert page.blacklist_table.model().rowCount() == 0


def test_settings_rows_keep_full_height_on_short_screen(qtbot):
    # Без прокрутки на невысоком экране строки формы сплющивались,
    # и текст в полях обрезался.
    page, *_ = make_page(qtbot)
    page.setFixedSize(830, 480)
    page.show()
    qtbot.waitExposed(page)

    for field in (page.last_pass_num_edit, page.preview_target_combo):
        assert field.height() >= field.sizeHint().height()


def test_settings_save_button_stays_visible_on_short_screen(qtbot):
    page, *_ = make_page(qtbot)
    page.setFixedSize(830, 480)
    page.show()
    qtbot.waitExposed(page)

    bottom = page.save_button.mapTo(page, page.save_button.rect().bottomLeft()).y()
    assert page.save_button.isVisible()
    assert bottom <= page.height()
    assert page.save_button.height() >= page.save_button.sizeHint().height()
