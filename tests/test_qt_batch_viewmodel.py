from pathlib import Path

from getpass_app.models.batch import (
    BatchOutputResult,
    BatchReview,
    BatchReviewRow,
)
from getpass_qt.viewmodels.batch_viewmodel import BatchViewModel


class FakePool:
    def __init__(self):
        self.started = []

    def start(self, worker):
        self.started.append(worker)


class FakeBatchService:
    def __init__(self):
        self.read_calls = []
        self.pass_parse_calls = []
        self.badge_parse_calls = []
        self.review_calls = []
        self.template_exports = []
        self.generate_calls = []
        self.review_with_error = False

    def read_csv(self, path):
        self.read_calls.append(path)
        return (("row",),)

    def parse_pass_rows(self, rows, defaults):
        self.pass_parse_calls.append((rows, dict(defaults)))
        return ({"plate": "А111АА78", "driver_full": "Иванов И.И."},)

    def parse_badge_rows(self, rows, folder, defaults):
        self.badge_parse_calls.append((rows, folder, dict(defaults)))
        return ({"tab_num": "01035", "fio": "ИВАНОВ И.И."},)

    def review(self, kind, items):
        self.review_calls.append((kind, tuple(items)))
        errors = ("bad",) if self.review_with_error else ()
        return BatchReview(
            kind=kind,
            rows=(
                BatchReviewRow(
                    row_number=2,
                    number="01035" if kind == "badge" else "А111АА78",
                    person="ИВАНОВ И.И." if kind == "badge" else "Иванов И.И.",
                    errors=errors,
                ),
            ),
        )

    def export_template(self, kind, path):
        self.template_exports.append((kind, path))

    def generate_pdf(self, kind, items, path, *, cancelled, progress):
        self.generate_calls.append((kind, tuple(items), path, cancelled))
        progress(1, 2)
        progress(2, 2)
        return BatchOutputResult(
            kind=kind,
            path=path,
            item_count=len(tuple(items)),
            page_count=2,
        )


def test_viewmodel_loads_vehicle_csv_with_owned_defaults(qtbot, tmp_path):
    service = FakeBatchService()
    pool = FakePool()
    vm = BatchViewModel(service, pool=pool)
    vm.set_pass_defaults(
        issue_date="12.09.2026",
        valid_until="12.09.2027",
        otb_post="Инженер",
        otb_name="Петров П.П.",
        is_temporary=False,
    )
    path = tmp_path / "passes.csv"

    assert vm.load_csv(str(path)) is True

    assert vm.kind == "pass"
    assert vm.source_path == str(path)
    assert vm.review.total == 1
    assert vm.can_generate is True
    defaults = service.pass_parse_calls[-1][1]
    assert defaults["issue_date"] == "12.09.2026"
    assert defaults["otb_name"] == "Петров П.П."


def test_switching_kind_clears_loaded_import_and_badge_uses_csv_directory(qtbot, tmp_path):
    service = FakeBatchService()
    vm = BatchViewModel(service, pool=FakePool())
    vm.load_csv(str(tmp_path / "passes.csv"))
    vm.set_kind("badge")
    vm.set_badge_defaults(
        park="ОСП ТП №8",
        issue_date="12.09.2026",
        valid_until="12.09.2027",
    )
    badge_path = tmp_path / "badges.csv"

    assert vm.source_path == ""
    assert vm.items == ()
    assert vm.review is None
    assert vm.load_csv(str(badge_path)) is True

    _rows, folder, defaults = service.badge_parse_calls[-1]
    assert folder == str(Path(badge_path).parent)
    assert defaults["park"] == "ОСП ТП №8"


def test_export_template_uses_selected_kind(qtbot):
    service = FakeBatchService()
    vm = BatchViewModel(service, pool=FakePool())
    vm.set_kind("badge")

    assert vm.export_template("badge-template.csv") is True

    assert service.template_exports == [("badge", "badge-template.csv")]


def test_generate_dispatches_worker_and_relays_progress_result_and_busy(qtbot):
    service = FakeBatchService()
    pool = FakePool()
    vm = BatchViewModel(service, pool=pool)
    vm.load_csv("passes.csv")
    busy = []
    progress = []
    results = []
    vm.busy_changed.connect(busy.append)
    vm.progress_changed.connect(lambda current, total: progress.append((current, total)))
    vm.output_succeeded.connect(results.append)

    assert vm.generate_pdf("passes.pdf") is True
    assert busy == [True]
    assert len(pool.started) == 1

    pool.started[0].run()

    assert progress == [(1, 2), (2, 2)]
    assert len(results) == 1
    assert results[0].path == "passes.pdf"
    assert busy == [True, False]
    assert vm.busy is False


def test_cancel_marks_current_worker_and_error_review_blocks_generation(qtbot):
    service = FakeBatchService()
    service.review_with_error = True
    pool = FakePool()
    vm = BatchViewModel(service, pool=pool)
    vm.load_csv("passes.csv")
    failures = []
    vm.operation_failed.connect(failures.append)

    assert vm.generate_pdf("passes.pdf") is False
    assert not pool.started
    assert failures == ["Исправьте ошибки импорта перед формированием PDF."]

    service.review_with_error = False
    vm.load_csv("passes.csv")
    assert vm.generate_pdf("passes.pdf") is True
    vm.cancel()

    assert pool.started[0].cancelled.is_set()
