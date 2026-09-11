import pytest

from getpass_app.models.vehicle_pass import (
    VehiclePassCommon,
    VehiclePassData,
    VehiclePassState,
)
from getpass_app.services.vehicle_pass_service import (
    VehiclePassOutputError,
    VehiclePassService,
)


def make_service(**overrides):
    defaults = {
        "lookup": lambda plate: None,
        "zone_values": lambda: [],
        "brand_values": lambda: [],
        "render": lambda data, common: ("front", data["num"], data["plate"]),
        "render_back": lambda: "back",
        "build_a4": lambda first, second=None: ("sheet", first, second),
    }
    defaults.update(overrides)
    return VehiclePassService(**defaults)


def valid_state(*, print_back=False, page_format="a4", second=False):
    return VehiclePassState(
        first=VehiclePassData(
            num="100-01",
            plate="А111АА78",
            brand="Лада",
            driver_position="водитель",
            driver_name="Иванов И.И.",
            territory="Парковка",
        ),
        second=(
            VehiclePassData(num="100-02", plate="В222ВВ78", brand="Volvo")
            if second
            else VehiclePassData(num="100-02")
        ),
        common=VehiclePassCommon(
            issue_date="12.09.2026",
            valid_until="12.09.2027",
        ),
        page_format=page_format,
        print_back=print_back,
    )


def output_service(calls, **overrides):
    defaults = {
        "journal": object(),
        "prepare": lambda journal, records, destination: calls.append(
            ("prepare", records, destination)
        ) or "operation-1",
        "confirm": lambda journal, operation_id: calls.append(("confirm", operation_id)),
        "cancel": lambda journal, operation_id: calls.append(("cancel", operation_id)),
        "save_document": lambda document, path: calls.append(("save", document, path)),
        "save_pdf_pages": lambda pages, path: calls.append(("save_pages", pages, path)),
        "print_one": lambda document, printer: calls.append(("print_one", document, printer)) or (True, ""),
        "print_two": lambda front, back, printer, confirm_flip=None: calls.append(
            ("print_two", front, back, printer, confirm_flip)
        ) or (True, ""),
        "update_cache": lambda records: calls.append(("cache", records)),
    }
    defaults.update(overrides)
    return make_service(**defaults)


def test_lookup_returns_only_vehicle_fields():
    service = make_service(
        lookup=lambda plate: {
            "brand": "Лада",
            "model": "Веста",
            "type": "легковой",
            "color": "белый",
            "d_fio": "СТАРЫЙ ВОДИТЕЛЬ",
            "d_phone": "123",
            "territory": "СТАРАЯ ЗОНА",
        }
    )

    assert service.lookup_vehicle("А111АА78") == {
        "brand": "Лада",
        "model": "Веста",
        "type": "легковой",
        "color": "белый",
    }


def test_lookup_none_stays_none():
    assert make_service().lookup_vehicle("А111АА78") is None


def test_zones_merge_defaults_and_history_without_duplicates():
    service = make_service(
        zone_values=lambda: ["Парковка", "Гостевая зона"],
        brand_values=lambda: ["Volvo", "Лада"],
    )

    assert service.zones() == (
        'ПТО "Шаврова"',
        "Парковка",
        'ПТО "Шаврова", Парковка',
        "Гостевая зона",
    )
    assert service.brands() == ("Volvo", "Лада")


def test_preview_uses_legacy_placeholder_renderer_contract():
    captured = []
    service = make_service(
        render=lambda data, common: captured.append((data, common)) or "preview"
    )

    result = service.render_preview(VehiclePassData(), VehiclePassCommon())

    assert result == "preview"
    assert captured[0][0]["num"] == "000-00"
    assert captured[0][0]["plate"] == "А 000 АА 00"
    assert captured[0][0]["driver_full"] == "Должность  Фамилия И.О."


def test_a4_builds_two_front_slots_and_matching_back_sheet():
    service = make_service()
    state = VehiclePassState(
        first=VehiclePassData(num="100-01", plate="А111АА78"),
        second=VehiclePassData(num="100-02", plate="В222ВВ78"),
        print_back=True,
    )

    front, back = service.build_documents(state)

    assert front == (
        "sheet",
        ("front", "100-01", "А111АА78"),
        ("front", "100-02", "В222ВВ78"),
    )
    assert back == ("sheet", "back", "back")


def test_a4_empty_second_pass_uses_only_first_slot():
    service = make_service()
    state = VehiclePassState(
        first=VehiclePassData(num="100-01", plate="А111АА78"),
        second=VehiclePassData(num="100-02"),
    )

    front, back = service.build_documents(state)

    assert front == ("sheet", ("front", "100-01", "А111АА78"), None)
    assert back is None


def test_a5_returns_single_existing_renderer_image_and_back():
    service = make_service()
    state = VehiclePassState(
        first=VehiclePassData(num="100-01", plate="А111АА78"),
        second=VehiclePassData(num="100-02", plate="В222ВВ78"),
        page_format="a5",
        print_back=True,
    )

    front, back = service.build_documents(state)

    assert front == ("front", "100-01", "А111АА78")
    assert back == "back"


def test_save_pdf_prepares_writes_confirms_then_updates_cache():
    calls = []
    service = output_service(calls)

    service.save_pdf(valid_state(), "out.pdf")

    assert [call[0] for call in calls] == ["prepare", "save", "confirm", "cache"]
    records = calls[0][1]
    assert records[0]["issue_date"] == "12.09.2026"
    assert records[0]["valid_until"] == "12.09.2027"
    assert records[0]["driver_full"] == "водитель Иванов И.И."


def test_save_with_back_uses_multi_page_pdf_writer():
    calls = []
    service = output_service(calls)

    service.save_pdf(valid_state(print_back=True), "out.pdf")

    assert [call[0] for call in calls] == ["prepare", "save_pages", "confirm", "cache"]
    assert len(calls[1][1]) == 2


def test_save_failure_cancels_and_does_not_confirm_or_cache():
    calls = []

    def fail_save(document, path):
        calls.append(("save", document, path))
        raise OSError("disk full")

    service = output_service(calls, save_document=fail_save)

    with pytest.raises(VehiclePassOutputError, match="disk full"):
        service.save_pdf(valid_state(), "out.pdf")

    assert [call[0] for call in calls] == ["prepare", "save", "cancel"]


def test_one_sided_print_prepares_prints_confirms_and_updates_cache():
    calls = []
    service = output_service(calls)

    service.print_passes(valid_state(), "Office Printer")

    assert [call[0] for call in calls] == ["prepare", "print_one", "confirm", "cache"]


def test_two_sided_print_uses_existing_duplex_helper():
    calls = []
    service = output_service(calls)
    confirm_flip = lambda: True

    service.print_passes(
        valid_state(print_back=True),
        "Office Printer",
        confirm_flip=confirm_flip,
    )

    assert [call[0] for call in calls] == ["prepare", "print_two", "confirm", "cache"]
    assert calls[1][-1] is confirm_flip


def test_print_failure_cancels_prepared_operation():
    calls = []
    service = output_service(
        calls,
        print_one=lambda document, printer: calls.append(
            ("print_one", document, printer)
        ) or (False, "printer offline"),
    )

    with pytest.raises(VehiclePassOutputError, match="printer offline"):
        service.print_passes(valid_state(), "Office Printer")

    assert [call[0] for call in calls] == ["prepare", "print_one", "cancel"]


def test_a5_issuance_records_only_the_printed_first_pass():
    calls = []
    service = output_service(calls)

    service.save_pdf(valid_state(page_format="a5", second=True), "out.pdf")

    assert len(calls[0][1]) == 1
    assert calls[0][1][0]["plate"] == "А111АА78"


def test_validation_rejects_output_before_prepare():
    calls = []
    service = output_service(calls)

    with pytest.raises(VehiclePassOutputError, match="государственный"):
        service.save_pdf(VehiclePassState(), "out.pdf")

    assert calls == []
