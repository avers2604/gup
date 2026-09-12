import threading

import pytest
from PIL import Image

from getpass_app.services.batch_service import (
    BatchCancelled,
    BatchOutputError,
    BatchService,
)


class FakeJournal:
    schema = type("Schema", (), {"keys": ["plate"], "table": "fake"})()


class BatchFakes:
    def __init__(self, events):
        self.events = events

    def render_pass(self, item, common):
        self.events.append(("render_pass", item["num"], common["issue_date"]))
        return Image.new("RGB", (20, 10), "white")

    def build_pass_sheet(self, first, second):
        self.events.append(("pass_sheet", second is not None))
        return Image.new("RGB", (40, 20), "white")

    def decorate_pass_sheet(self, _image):
        self.events.append(("decorate",))

    def render_badge(self, item):
        self.events.append(("render_badge", item["tab_num"]))
        return Image.new("RGB", (10, 10), "white")

    def build_badge_grid(self, images):
        self.events.append(("badge_grid", len(images)))
        return Image.new("RGB", (30, 30), "white")

    def save_pages(self, pages, path):
        count = 0
        for page in pages:
            assert isinstance(page, Image.Image)
            count += 1
        self.events.append(("save", path, count))
        return count

    def prepare(self, journal, records, path):
        self.events.append(("prepare", path, tuple(records)))
        return "op-1"

    def confirm(self, journal, operation_id):
        self.events.append(("confirm", operation_id))

    def cancel(self, journal, operation_id):
        self.events.append(("cancel", operation_id))

    def update_cache(self, items):
        self.events.append(("cache", tuple(item["plate"] for item in items)))


def _service(events, **overrides):
    fakes = BatchFakes(events)
    kwargs = {
        "pass_journal": FakeJournal(),
        "badge_journal": FakeJournal(),
        "render_pass": fakes.render_pass,
        "build_pass_sheet": fakes.build_pass_sheet,
        "decorate_pass_sheet": fakes.decorate_pass_sheet,
        "render_badge": fakes.render_badge,
        "build_badge_grid": fakes.build_badge_grid,
        "save_pdf_pages": fakes.save_pages,
        "prepare": fakes.prepare,
        "confirm": fakes.confirm,
        "cancel": fakes.cancel,
        "update_cache": fakes.update_cache,
    }
    kwargs.update(overrides)
    return BatchService(**kwargs)


def _pass_item(number, plate):
    return {
        "num": number,
        "plate": plate,
        "issue_date": "12.09.2026",
        "valid_until": "12.09.2027",
        "otb_post": "Инженер",
        "otb_name": "Петров П.П.",
        "is_temporary": False,
        "territory": "Парк",
        "driver_full": "Иванов И.И.",
    }


def _badge_item(number):
    return {
        "tab_num": number,
        "fio": f"Employee {number}",
        "issue_date": "12.09.2026",
        "valid_until": "12.09.2027",
    }


def test_vehicle_batch_packs_two_per_page_and_updates_cache_after_confirm():
    events = []
    service = _service(events)
    items = tuple(_pass_item(f"00{i}-26", f"A{i}") for i in range(1, 4))
    progress = []

    result = service.generate_pdf(
        "pass",
        items,
        "passes.pdf",
        cancelled=threading.Event(),
        progress=lambda current, total: progress.append((current, total)),
    )

    assert result.item_count == 3
    assert result.page_count == 2
    assert progress == [(1, 2), (2, 2)]
    assert [event for event in events if event[0] == "pass_sheet"] == [
        ("pass_sheet", True),
        ("pass_sheet", False),
    ]
    prepare = next(event for event in events if event[0] == "prepare")
    assert prepare[2][0]["zone"] == "Парк"
    assert prepare[2][0]["driver"] == "Иванов И.И."
    assert events.index(("confirm", "op-1")) < events.index(
        ("cache", ("A1", "A2", "A3"))
    )


def test_badge_batch_packs_nine_per_page_without_vehicle_cache_update():
    events = []
    service = _service(events)
    items = tuple(_badge_item(str(index)) for index in range(10))

    result = service.generate_pdf(
        "badge",
        items,
        "badges.pdf",
        cancelled=threading.Event(),
    )

    assert result.page_count == 2
    assert [event for event in events if event[0] == "badge_grid"] == [
        ("badge_grid", 9),
        ("badge_grid", 1),
    ]
    assert not any(event[0] == "cache" for event in events)


def test_cancellation_between_pages_cancels_prepared_operation():
    events = []
    cancelled = threading.Event()
    service = _service(events)
    items = tuple(_pass_item(f"00{i}-26", f"A{i}") for i in range(1, 4))

    def progress(current, total):
        if current == 1:
            cancelled.set()

    with pytest.raises(BatchCancelled):
        service.generate_pdf(
            "pass",
            items,
            "passes.pdf",
            cancelled=cancelled,
            progress=progress,
        )

    assert ("cancel", "op-1") in events
    assert not any(event[0] == "confirm" for event in events)
    assert not any(event[0] == "cache" for event in events)


def test_output_failure_cancels_prepared_operation_and_wraps_error():
    events = []

    def fail_save(_pages, _path):
        raise OSError("disk full")

    service = _service(events, save_pdf_pages=fail_save)

    with pytest.raises(BatchOutputError, match="disk full"):
        service.generate_pdf(
            "pass",
            (_pass_item("001-26", "A1"),),
            "passes.pdf",
            cancelled=threading.Event(),
        )

    assert ("cancel", "op-1") in events
    assert not any(event[0] == "confirm" for event in events)


def test_confirm_failure_stays_recoverable_and_is_not_cancelled():
    events = []

    def fail_confirm(_journal, operation_id):
        events.append(("confirm", operation_id))
        raise RuntimeError("journal busy")

    service = _service(events, confirm=fail_confirm)

    with pytest.raises(BatchOutputError, match="journal busy"):
        service.generate_pdf(
            "pass",
            (_pass_item("001-26", "A1"),),
            "passes.pdf",
            cancelled=threading.Event(),
        )

    assert ("confirm", "op-1") in events
    assert not any(event[0] == "cancel" for event in events)
    assert not any(event[0] == "cache" for event in events)


def test_empty_batch_is_rejected_before_prepare():
    events = []
    service = _service(events)

    with pytest.raises(BatchOutputError, match="Нечего"):
        service.generate_pdf(
            "pass",
            (),
            "passes.pdf",
            cancelled=threading.Event(),
        )

    assert not events
