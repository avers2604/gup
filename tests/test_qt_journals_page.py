from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QLineEdit, QPushButton, QTableView

from getpass_app.models.journal import JournalField, JournalRow, JournalSnapshot
from getpass_qt.viewmodels.journal_viewmodel import JournalViewModel
from getpass_qt.views.journals import JournalsPage


class FakePageJournalService:
    def __init__(self):
        self.revoked = []
        self.updated = []

    def journal_keys(self):
        return ("pass", "badge")

    def snapshot(
        self,
        journal_key,
        filters,
        *,
        sort_key=None,
        sort_reverse=False,
        page=0,
        page_size=100,
    ):
        if journal_key == "pass":
            fields = (
                JournalField("id", "ID", 0),
                JournalField("plate", "Номер машины", 110, "center"),
                JournalField("zone", "Зона допуска", 150),
                JournalField("driver", "Водитель", 240),
                JournalField("status", "Статус", 115, "center"),
            )
            values = {
                "id": "p1",
                "plate": "А111АА78",
                "zone": "Парковка",
                "driver": "Иванов Иван",
                "status": "действует",
            }
            state = "active"
            name = "Журнал пропусков ТС"
        else:
            fields = (
                JournalField("id", "ID", 0),
                JournalField("tab_num", "Табельный номер", 105),
                JournalField("role", "Должность", 180),
                JournalField("park", "Подразделение", 200),
                JournalField("status", "Статус", 115),
            )
            values = {
                "id": "b1",
                "tab_num": "01035",
                "role": "ВОДИТЕЛЬ",
                "park": "ТП-5",
                "status": "действует",
            }
            state = "unknown"
            name = "Журнал постоянных бейджей"
        return JournalSnapshot(
            journal_key=journal_key,
            journal_name=name,
            fields=fields,
            rows=(JournalRow(values["id"], values, state),),
            total_records=1,
            filtered_records=1,
            page=0,
            page_size=page_size,
            page_count=1,
        )

    def distinct(self, journal_key, key):
        values = {
            ("pass", "zone"): ("Парковка",),
            ("badge", "role"): ("ВОДИТЕЛЬ",),
            ("badge", "park"): ("ТП-5",),
        }
        return values.get((journal_key, key), ())

    def update_record(self, journal_key, record_id, values, expected):
        self.updated.append((journal_key, record_id, values, expected))

    def revoke(self, journal_key, ids, reason):
        self.revoked.append((journal_key, tuple(ids), reason))

    def history(self, journal_key, record_id):
        return ()

    def export(self, journal_key, rows, path):
        return len(tuple(rows))

    def add_revoked_to_blacklist(self, journal_key, ids, reason):
        return len(tuple(ids))


def _page(qtbot):
    vm = JournalViewModel(FakePageJournalService())
    page = JournalsPage(
        vm,
        save_dialog=lambda: "",
        ask_revoke_reason=lambda count: None,
    )
    qtbot.addWidget(page)
    page.show()
    return page, vm


def test_journals_page_uses_qt_model_view_table(qtbot):
    page, _ = _page(qtbot)

    table = page.findChild(QTableView, "JournalTable")
    assert table is page.table
    assert table.model().rowCount() == 1
    assert table.model().data(table.model().index(0, 0)) == "А111АА78"
    assert page.findChild(QLineEdit, "JournalSearch") is page.search_edit


def test_pass_and_badge_journals_expose_schema_specific_filters(qtbot):
    page, _ = _page(qtbot)

    assert set(page.extra_filters) == {"zone", "driver"}

    badge_index = page.journal_combo.findData("badge")
    page.journal_combo.setCurrentIndex(badge_index)
    qtbot.wait(1)

    assert set(page.extra_filters) == {"park", "role"}
    assert page.findChild(QComboBox, "JournalFilterRole") is page.extra_filters["role"]


def test_row_selection_enables_record_actions(qtbot):
    page, _ = _page(qtbot)
    edit = page.findChild(QPushButton, "JournalEditButton")
    revoke = page.findChild(QPushButton, "JournalRevokeButton")

    assert edit.isEnabled() is False
    assert revoke.isEnabled() is False

    page.table.selectRow(0)
    qtbot.wait(1)

    assert edit.isEnabled() is True
    assert revoke.isEnabled() is True


def test_status_is_visible_as_text_not_only_color(qtbot):
    page, _ = _page(qtbot)
    model = page.table.model()
    status_column = next(
        index
        for index in range(model.columnCount())
        if model.headerData(index, Qt.Orientation.Horizontal) == "Статус"
    )

    assert model.data(model.index(0, status_column)) == "действует"

    page.journal_combo.setCurrentIndex(page.journal_combo.findData("badge"))
    qtbot.wait(1)
    model = page.table.model()
    status_column = next(
        index
        for index in range(model.columnCount())
        if model.headerData(index, Qt.Orientation.Horizontal) == "Статус"
    )
    assert model.data(model.index(0, status_column)) == "нет срока"
