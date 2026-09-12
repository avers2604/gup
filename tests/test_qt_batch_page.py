from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QTableView

from getpass_app.models.batch import (
    BatchOutputResult,
    BatchReview,
    BatchReviewRow,
)
from getpass_qt.models.batch_review_table_model import BatchReviewTableModel
from getpass_qt.views.batch import BatchPage


class FakeBatchViewModel(QObject):
    kind_changed = Signal(str)
    review_changed = Signal(object)
    busy_changed = Signal(bool)
    progress_changed = Signal(int, int)
    output_succeeded = Signal(object)
    operation_failed = Signal(str)

    def __init__(self):
        super().__init__()
        self.kind = "pass"
        self.review = None
        self.busy = False
        self.pass_defaults = []
        self.badge_defaults = []
        self.loaded = []
        self.exported = []
        self.generated = []
        self.cancelled = 0

    @property
    def can_generate(self):
        return self.review is not None and self.review.can_generate and not self.busy

    def set_kind(self, kind):
        self.kind = kind
        self.review = None
        self.kind_changed.emit(kind)
        self.review_changed.emit(None)

    def set_pass_defaults(self, **values):
        self.pass_defaults.append(values)

    def set_badge_defaults(self, **values):
        self.badge_defaults.append(values)

    def load_csv(self, path):
        self.loaded.append(path)
        return True

    def export_template(self, path):
        self.exported.append(path)
        return True

    def generate_pdf(self, path):
        self.generated.append(path)
        return True

    def cancel(self):
        self.cancelled += 1


def _review(*, warnings=(), errors=()):
    return BatchReview(
        kind="pass",
        rows=(
            BatchReviewRow(
                row_number=2,
                number="А111АА78",
                person="Иванов И.И.",
                warnings=tuple(warnings),
                errors=tuple(errors),
            ),
        ),
    )


def _page(qtbot, vm, **callbacks):
    page = BatchPage(vm, **callbacks)
    qtbot.addWidget(page)
    return page


def test_batch_page_uses_model_view_and_switches_kind(qtbot):
    vm = FakeBatchViewModel()
    page = _page(qtbot, vm)

    assert isinstance(page.review_table, QTableView)
    page.kind_combo.setCurrentIndex(1)

    assert vm.kind == "badge"
    assert page.badge_defaults.isVisible() is False

    review = BatchReview(
        kind="badge",
        rows=(BatchReviewRow(2, "01035", "ИВАНОВ И.И."),),
    )
    vm.review = review
    vm.review_changed.emit(review)

    assert isinstance(page.review_table.model(), BatchReviewTableModel)
    assert page.review_table.model().rowCount() == 1
    assert "Записей: 1" in page.summary_label.text()


def test_import_applies_vehicle_defaults_before_loading_csv(qtbot):
    vm = FakeBatchViewModel()
    page = _page(qtbot, vm, choose_csv=lambda _kind: "passes.csv")
    page.issue_date_edit.setText("12.09.2026")
    page.valid_until_edit.setText("12.09.2027")
    page.otb_post_edit.setText("Инженер")
    page.otb_name_edit.setText("Петров П.П.")
    page.temporary_check.setChecked(True)

    page.import_button.click()

    assert vm.loaded == ["passes.csv"]
    assert vm.pass_defaults[-1] == {
        "issue_date": "12.09.2026",
        "valid_until": "12.09.2027",
        "otb_post": "Инженер",
        "otb_name": "Петров П.П.",
        "is_temporary": True,
    }


def test_warning_review_requires_confirmation_before_pdf_generation(qtbot):
    vm = FakeBatchViewModel()
    confirmations = []
    page = _page(
        qtbot,
        vm,
        choose_pdf=lambda _kind, _count: "passes.pdf",
        confirm_warnings=lambda count: confirmations.append(count) or True,
    )
    review = _review(warnings=("Совпадение",))
    vm.review = review
    vm.review_changed.emit(review)

    page.generate_button.click()

    assert confirmations == [1]
    assert vm.generated == ["passes.pdf"]


def test_errors_disable_generation_and_busy_state_drives_progress_cancel(qtbot):
    vm = FakeBatchViewModel()
    page = _page(qtbot, vm)
    review = _review(errors=("Некорректный номер",))
    vm.review = review
    vm.review_changed.emit(review)

    assert page.generate_button.isEnabled() is False

    vm.busy = True
    vm.busy_changed.emit(True)
    vm.progress_changed.emit(2, 5)

    assert page.progress_bar.maximum() == 5
    assert page.progress_bar.value() == 2
    assert page.cancel_button.isEnabled() is True
    page.cancel_button.click()
    assert vm.cancelled == 1

    vm.busy = False
    vm.busy_changed.emit(False)
    assert page.cancel_button.isEnabled() is False


def test_output_result_updates_status_text(qtbot):
    vm = FakeBatchViewModel()
    page = _page(qtbot, vm)

    vm.output_succeeded.emit(
        BatchOutputResult("pass", "passes.pdf", item_count=3, page_count=2)
    )

    assert "3" in page.status_label.text()
    assert "passes.pdf" in page.status_label.text()
