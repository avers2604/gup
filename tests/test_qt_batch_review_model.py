from PySide6.QtCore import Qt

from getpass_app.models.batch import BatchReview, BatchReviewRow
from getpass_qt.models.batch_review_table_model import BatchReviewTableModel


def _review():
    return BatchReview(
        kind="pass",
        rows=(
            BatchReviewRow(
                row_number=2,
                number="А111АА78",
                person="Иванов И.И.",
                warnings=("Совпадение в журнале",),
            ),
            BatchReviewRow(
                row_number=3,
                number="Б222ББ78",
                person="Петров П.П.",
                errors=("Некорректный номер",),
            ),
        ),
    )


def test_batch_review_model_exposes_four_columns_and_summary_text():
    model = BatchReviewTableModel(_review())

    assert model.rowCount() == 2
    assert model.columnCount() == 4
    assert model.headerData(0, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) == "Строка"
    assert model.headerData(1, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) == "Номер"
    assert model.headerData(2, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) == "Сотрудник / водитель"
    assert model.headerData(3, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) == "Проверка"

    assert model.data(model.index(0, 0), Qt.ItemDataRole.DisplayRole) == 2
    assert model.data(model.index(0, 1), Qt.ItemDataRole.DisplayRole) == "А111АА78"
    assert model.data(model.index(0, 2), Qt.ItemDataRole.DisplayRole) == "Иванов И.И."
    assert model.data(model.index(0, 3), Qt.ItemDataRole.DisplayRole) == "Совпадение в журнале"


def test_batch_review_model_exposes_row_state_role_and_can_reset():
    model = BatchReviewTableModel(_review())

    state_role = Qt.ItemDataRole.UserRole + 1
    assert model.data(model.index(0, 0), state_role) == "warning"
    assert model.data(model.index(1, 0), state_role) == "error"
    assert model.row(1).number == "Б222ББ78"

    empty = BatchReview(kind="badge", rows=())
    model.set_review(empty)

    assert model.review is empty
    assert model.rowCount() == 0
