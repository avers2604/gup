# PySide6 Phase 2 Vehicle Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the PySide6 `vehicle` migration placeholder with a real vehicle-pass workflow that can edit two passes, render the unchanged existing pass template, save PDF, and print while the Tkinter production entry point remains available.

**Architecture:** Add vehicle-pass state and orchestration to the UI-independent `getpass_app` layer, expose that state through a focused MVVM-lite `VehiclePassViewModel`, and implement the Variant-A two-column PySide6 page. The service calls the existing `getpass_core.render`, `printing`, `issuance`, and SQLite-backed journal APIs through injectable dependencies; the renderer itself remains protected and unmodified. `MainWindow` owns page composition only and does not call renderer, SQLite, or printing functions directly.

**Tech Stack:** Python 3.13/3.14, PySide6 6.11.x, Pillow, existing `getpass_core`, SQLite, pytest, pytest-qt.

**Spec:** `docs/superpowers/specs/2026-09-11-pyside6-v2-ui-design.md`

## Global Constraints

- Keep `pass_generator.py` as the production Tkinter entry point during Phase 2.
- Do not modify `getpass_core/render.py`, `getpass_core/blank.py`, `getpass_core/fonts.py`, `assets/`, `fonts/`, or `fronts/`; renderer-contract tests must remain green.
- Do not change SQLite schema or migrations.
- Reuse the GET palette from `getpass_design.tokens`; no independent Qt color constants.
- Vehicle lookup may reuse only vehicle data (`brand`, `model`, `type`, `color`); it must not restore previous driver data.
- The printed/rendered pass must continue to be produced by `getpass_core.render.render_pass()` and `render_pass_back()`.
- Phase 2 may build a Qt preview executable in CI but must not switch `build-exe.yml`, `release.yml`, or Inno Setup to Qt production packaging.
- User output operations must preserve durable issuance semantics: prepare before external output, confirm after success, cancel after failure.

---

## File Map

**Create**
- `getpass_app/models/vehicle_pass.py` — immutable/passable vehicle form state and common details.
- `getpass_app/services/vehicle_pass_service.py` — lookup, validation, rendering, document building, save/print orchestration.
- `getpass_qt/viewmodels/vehicle_pass_viewmodel.py` — Qt signals and editable state for the vehicle workflow.
- `getpass_qt/views/vehicle_pass.py` — Variant-A vehicle page.
- `getpass_qt/widgets/image_preview.py` — PIL-to-QPixmap preview widget with fit-to-window behavior.
- `tests/test_vehicle_pass_model.py`
- `tests/test_vehicle_pass_service.py`
- `tests/test_qt_vehicle_viewmodel.py`
- `tests/test_qt_vehicle_page.py`

**Modify**
- `getpass_qt/main_window.py` — replace only the `vehicle` migration page with `VehiclePassPage`.
- `getpass_qt/theme/stylesheet.py` — add semantic styles for fields, segmented buttons, action bar, validation, preview surface.
- `getpass_qt/app.py` — construct/inject `VehiclePassService`; strengthen `--self-test` to exercise the vehicle page without output side effects.
- `README.md` — describe Phase 2 preview scope and commands.

---

### Task 1: Vehicle-pass application model and validation

**Files:**
- Create: `getpass_app/models/vehicle_pass.py`
- Test: `tests/test_vehicle_pass_model.py`

**Interfaces:**
- Produces `VehiclePassData`, `VehiclePassCommon`, `VehiclePassState`, `ValidationIssue`.
- Produces `VehiclePassData.to_renderer_dict(*, placeholder: bool = False) -> dict[str, object]`.
- Produces `VehiclePassCommon.to_renderer_dict() -> dict[str, object]`.
- Produces `validate_vehicle_state(state: VehiclePassState) -> tuple[ValidationIssue, ...]`.
- Later tasks consume exactly these names.

- [ ] **Step 1: Write failing model tests**

```python
from getpass_app.models.vehicle_pass import (
    VehiclePassCommon,
    VehiclePassData,
    VehiclePassState,
    validate_vehicle_state,
)


def test_renderer_dict_normalizes_plate_without_driver_restore():
    data = VehiclePassData(
        num="100-01",
        plate="а111аа78",
        brand="Лада",
        model="Веста",
        vehicle_type="легковой",
        color="белый",
        driver_position="водитель",
        driver_name="Иванов И.И.",
        phone="+7 999 000-00-00",
        territory='ПТО "Шаврова"',
    )
    result = data.to_renderer_dict()
    assert result["plate"] == "А111АА78"
    assert result["type"] == "легковой"
    assert result["driver_full"] == "водитель Иванов И.И."
    assert result["phone"] == "+7 999 000-00-00"


def test_second_empty_pass_is_allowed_but_first_plate_is_required():
    state = VehiclePassState(first=VehiclePassData(), second=VehiclePassData())
    issues = validate_vehicle_state(state)
    assert [(i.field, i.message) for i in issues] == [
        ("first.plate", "Укажите государственный регистрационный знак."),
    ]


def test_nonempty_second_pass_requires_plate():
    state = VehiclePassState(
        first=VehiclePassData(plate="А111АА78"),
        second=VehiclePassData(num="100-02", brand="Лада"),
    )
    assert any(i.field == "second.plate" for i in validate_vehicle_state(state))


def test_common_renderer_contract_uses_existing_keys():
    common = VehiclePassCommon(
        issue_date="12.09.2026",
        valid_until="12.09.2027",
        is_temporary=True,
        otb_post="Начальник ОТБ",
        otb_name="Петров П.П.",
    )
    assert common.to_renderer_dict() == {
        "issue_date": "12.09.2026",
        "valid_until": "12.09.2027",
        "is_temporary": True,
        "otb_post": "Начальник ОТБ",
        "otb_name": "Петров П.П.",
    }
```

- [ ] **Step 2: Run the tests and confirm RED**

Run: `python -m pytest tests/test_vehicle_pass_model.py -v`

Expected: import failure because `getpass_app.models.vehicle_pass` does not exist.

- [ ] **Step 3: Implement the minimal model**

Use frozen dataclasses. Required public shape:

```python
@dataclass(frozen=True)
class VehiclePassData:
    num: str = ""
    plate: str = ""
    brand: str = ""
    model: str = ""
    vehicle_type: str = ""
    color: str = ""
    driver_position: str = ""
    driver_name: str = ""
    phone: str = ""
    territory: str = ""

    @property
    def is_empty(self) -> bool:
        return not any((self.plate.strip(), self.brand.strip(), self.model.strip(),
                        self.vehicle_type.strip(), self.color.strip()))

    def to_renderer_dict(self, *, placeholder: bool = False) -> dict[str, object]:
        ...


@dataclass(frozen=True)
class VehiclePassCommon:
    issue_date: str = ""
    valid_until: str = ""
    is_temporary: bool = False
    otb_post: str = ""
    otb_name: str = ""

    def to_renderer_dict(self) -> dict[str, object]:
        ...


@dataclass(frozen=True)
class VehiclePassState:
    first: VehiclePassData = field(default_factory=VehiclePassData)
    second: VehiclePassData = field(default_factory=VehiclePassData)
    common: VehiclePassCommon = field(default_factory=VehiclePassCommon)
    page_format: Literal["a4", "a5"] = "a4"
    print_back: bool = False


@dataclass(frozen=True)
class ValidationIssue:
    field: str
    message: str
```

Use existing `getpass_core.domain.normalize_plate()` for renderer output. Placeholder values must match the legacy preview contract: number `000-00`, plate `А 000 АА 00`, and driver `Должность  Фамилия И.О.` only when requested.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_vehicle_pass_model.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `feat: add vehicle pass application model`

---

### Task 2: VehiclePassService lookup, suggestions, preview and document composition

**Files:**
- Create: `getpass_app/services/vehicle_pass_service.py`
- Test: `tests/test_vehicle_pass_service.py`

**Interfaces:**
- Consumes Task 1 model types.
- Produces `VehiclePassService.lookup_vehicle(plate: str) -> dict[str, str] | None`.
- Produces `VehiclePassService.zones() -> tuple[str, ...]` and `brands() -> tuple[str, ...]`.
- Produces `render_preview(data, common) -> PIL.Image.Image`.
- Produces `build_documents(state) -> tuple[PIL.Image.Image, PIL.Image.Image | None]` where the first item is the printable front page/sheet and the optional second item is the printable reverse page/sheet.

- [ ] **Step 1: Write failing service tests with injected fakes**

Cover all of these behaviors:

```python
def test_lookup_returns_only_vehicle_fields():
    service = service_with_lookup({
        "brand": "Лада", "model": "Веста", "type": "легковой", "color": "белый",
        "d_fio": "СТАРЫЙ ВОДИТЕЛЬ", "d_phone": "123", "territory": "СТАРАЯ ЗОНА",
    })
    assert service.lookup_vehicle("А111АА78") == {
        "brand": "Лада", "model": "Веста", "type": "легковой", "color": "белый",
    }


def test_a4_builds_two_pass_front_sheet_and_matching_back_sheet(): ...
def test_a4_with_empty_second_pass_builds_one_front_slot(): ...
def test_a5_builds_single_pass_without_a4_composition(): ...
def test_print_back_false_returns_no_back_document(): ...
def test_preview_calls_existing_renderer_with_placeholder_contract(): ...
```

For back-side A4, create two `render_pass_back()` images and compose them through the existing `build_pass_a4_sheet()` so front/back sheet geometry stays identical. For A5, return the individual pass image and individual back image.

- [ ] **Step 2: Confirm RED**

Run: `python -m pytest tests/test_vehicle_pass_service.py -v`

Expected: import failure for the new service.

- [ ] **Step 3: Implement service with dependency injection**

Constructor defaults must bind to existing core functions, but tests can replace them:

```python
class VehiclePassService:
    def __init__(
        self,
        *,
        lookup=lookup_car,
        zone_values=None,
        brand_values=known_car_brands,
        render=R.render_pass,
        render_back=R.render_pass_back,
        build_a4=R.build_pass_a4_sheet,
        ...,
    ) -> None:
        ...
```

Default zones: legacy constants `ПТО "Шаврова"`, `Парковка`, `ПТО "Шаврова", Парковка`, followed by distinct historical `zone` values from `PASS_JOURNAL`, deduplicated while preserving stable ordering.

`lookup_vehicle()` must explicitly project only `brand`, `model`, `type`, and `color`. Never return driver/phone/territory from the cache.

- [ ] **Step 4: GREEN**

Run: `python -m pytest tests/test_vehicle_pass_service.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `feat: add vehicle pass rendering service`

---

### Task 3: Durable PDF save and print orchestration

**Files:**
- Modify: `getpass_app/services/vehicle_pass_service.py`
- Modify: `tests/test_vehicle_pass_service.py`

**Interfaces:**
- Produces `save_pdf(state: VehiclePassState, path: str) -> None`.
- Produces `print_passes(state: VehiclePassState, printer: str, *, confirm_flip: Callable[[], bool] | None = None) -> None`.
- Both methods raise `VehiclePassOutputError` on output failure after cancelling the prepared issuance.
- Both methods update the car cache only after successful issuance confirmation.

- [ ] **Step 1: Add RED tests for issuance transaction ordering**

Test exact call order with fakes:

```python
def test_save_pdf_prepares_writes_confirms_then_updates_cache():
    calls = []
    # injected prepare/save/confirm/update functions append to calls
    service.save_pdf(valid_state(), "out.pdf")
    assert calls == ["prepare", "save", "confirm", "cache"]


def test_save_failure_cancels_and_does_not_confirm_or_cache():
    ...
    assert calls == ["prepare", "save", "cancel"]


def test_print_failure_cancels_prepared_operation(): ...
def test_two_sided_print_uses_existing_print_pass_two_sided(): ...
def test_one_sided_print_uses_existing_send_image_to_printer(): ...
```

Build journal records from non-empty passes by merging `to_renderer_dict()` with `issue_date` and `valid_until`. Do not insert directly into SQLite; `issuance.confirm()` remains the durable commit point.

- [ ] **Step 2: Confirm RED**

Run the new output tests only and verify missing methods.

- [ ] **Step 3: Implement minimal orchestration**

For save:
1. `validate_vehicle_state()`; reject invalid state before preparing.
2. `issuance.prepare(PASS_JOURNAL, records, path)`.
3. Build documents.
4. Save one page with `printing.save_document()` or two PDF pages with `printing.save_pdf_pages()`.
5. `issuance.confirm(...)`.
6. `update_cars_cache(records)`.
7. On any exception after prepare, attempt `issuance.cancel(...)`, then raise `VehiclePassOutputError` preserving the original message.

For print:
1. Prepare using printer name as destination.
2. Build documents.
3. One-sided: `send_image_to_printer(front, printer)`.
4. Two-sided: `print_pass_two_sided(front, back, printer, confirm_flip=...)`.
5. Treat `(False, error)` as failure and cancel.
6. Confirm and update cache only on success.

- [ ] **Step 4: GREEN plus legacy issuance regression suite**

Run:
`python -m pytest tests/test_vehicle_pass_service.py tests/test_issuance_recovery.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `feat: add durable vehicle pass output service`

---

### Task 4: VehiclePassViewModel

**Files:**
- Create: `getpass_qt/viewmodels/vehicle_pass_viewmodel.py`
- Test: `tests/test_qt_vehicle_viewmodel.py`

**Interfaces:**
- Consumes `VehiclePassService` and Task 1 models.
- Produces Qt signals: `state_changed`, `preview_changed(object)`, `validation_changed(object)`, `busy_changed(bool)`, `operation_succeeded(str)`, `operation_failed(str)`.
- Produces setters by semantic field, not widget references.
- Produces `sync_second_number()`, `autocomplete_vehicle(slot)`, `refresh_preview()`, `save_pdf(path)`, `print_passes(printer, confirm_flip=None)`.

- [ ] **Step 1: Write RED ViewModel tests**

Required cases:
- default route state has two empty passes, `page_format="a4"`, `print_back=False`;
- `set_pass_field("first", "plate", "а111аа78")` stores uppercase input and emits `state_changed`;
- autocomplete fills only blank vehicle fields and never driver/phone/territory;
- `sync_second_number()` uses existing `getpass_core.domain.increment_number()`;
- invalid save emits/raises validation before service output;
- service preview result is emitted unchanged;
- page-format change from A4 to A5 keeps second-pass data but output service receives the selected format.

- [ ] **Step 2: Confirm RED**

Run: `python -m pytest tests/test_qt_vehicle_viewmodel.py -v`

- [ ] **Step 3: Implement ViewModel**

Keep mutable UI state private and expose immutable `VehiclePassState` snapshots through a `state` property. ViewModel may import PySide6, but `getpass_app` must remain PySide6-free.

Do not put file dialogs, message boxes, QPixmaps, or widget references in the ViewModel.

- [ ] **Step 4: GREEN**

Run: `python -m pytest tests/test_qt_vehicle_viewmodel.py tests/test_settings_service.py -v`

- [ ] **Step 5: Commit**

Commit message: `feat: add vehicle pass view model`

---

### Task 5: Reusable image preview widget

**Files:**
- Create: `getpass_qt/widgets/image_preview.py`
- Test: `tests/test_qt_vehicle_page.py`

**Interfaces:**
- Produces `ImagePreview.set_pil_image(image: PIL.Image.Image | None) -> None`.
- Produces `ImagePreview.has_image: bool`.
- Rescales from the original image on resize without mutating the PIL source.

- [ ] **Step 1: Add RED widget tests**

Verify a known PIL image becomes a non-null pixmap and survives widget resize while preserving aspect ratio. Verify `None` clears the pixmap and shows the empty-state label.

- [ ] **Step 2: Confirm RED**

Run the two preview tests.

- [ ] **Step 3: Implement using `PIL.ImageQt.ImageQt` → `QImage` → `QPixmap`**

Do not save temporary files. Keep the original PIL image reference for resize-driven re-rendering.

- [ ] **Step 4: GREEN**

Run the preview tests.

- [ ] **Step 5: Commit**

Commit message: `feat: add Qt image preview widget`

---

### Task 6: Variant-A VehiclePassPage

**Files:**
- Create: `getpass_qt/views/vehicle_pass.py`
- Modify: `getpass_qt/theme/stylesheet.py`
- Test: `tests/test_qt_vehicle_page.py`

**Interfaces:**
- Consumes `VehiclePassViewModel` and `ImagePreview`.
- Exposes stable object names for tests: `VehiclePassPage`, `PassSlotTabs`, `VehiclePreview`, `SavePdfButton`, `PrintButton`, `PrintSettings`.
- Emits `save_pdf_requested` only through a file-dialog adapter passed to the page constructor; tests inject a deterministic adapter.

- [ ] **Step 1: Write RED page tests**

Verify the page contains:
- left form area and right sticky preview;
- segmented/tabs controls `Пропуск №1` and `Пропуск №2`;
- fields for blank number, plate, brand, model, type, color, driver position/FIO/phone, territory;
- common details for issue date, valid-until, temporary flag, OTB position/name;
- compact print settings A4/A5 + reverse-side checkbox;
- primary `Напечатать` and secondary `Сохранить PDF` actions;
- preview target selector 1/2;
- no batch/journal/export buttons inside the main form.

Interaction tests:
- editing plate updates ViewModel;
- focus-out/autocomplete fills brand/model/type/color only;
- switching pass slot edits the correct state;
- validation marks the plate field through a semantic `invalid=true` property;
- preview signal updates `ImagePreview`;
- print button delegates to ViewModel rather than core printing directly.

- [ ] **Step 2: Confirm RED**

Run: `python -m pytest tests/test_qt_vehicle_page.py -v`

- [ ] **Step 3: Implement page and semantic QSS**

Use a `QSplitter`/horizontal layout with approximately 55% form / 45% preview at normal desktop widths. Form sections: `Транспортное средство`, `Водитель`, `Реквизиты`, collapsed/compact `Параметры печати`. Use GET semantic tokens only.

Use `QTimer(singleShot=True, interval=150)` on input changes to debounce preview rendering. Preview rendering still calls the existing renderer through the ViewModel/service; no alternate Qt drawing code is allowed.

- [ ] **Step 4: GREEN**

Run the page/ViewModel/service tests together.

- [ ] **Step 5: Commit**

Commit message: `feat: build PySide6 vehicle pass page`

---

### Task 7: MainWindow integration and safe preview self-test

**Files:**
- Modify: `getpass_qt/main_window.py`
- Modify: `getpass_qt/app.py`
- Modify: `tests/test_qt_navigation.py`
- Modify: `tests/test_qt_entrypoint.py`

**Interfaces:**
- `MainWindow` receives a `VehiclePassViewModel` dependency and installs `VehiclePassPage` for route `vehicle`; all other migration pages remain unchanged.
- `python -m getpass_qt --self-test` must navigate dashboard → vehicle, set deterministic sample state, render a preview, assert a non-empty preview, and exit 0 without saving, printing, or changing persistent settings.

- [ ] **Step 1: Add RED integration tests**

Required assertions:
- `window.stack.widget(vehicle_index)` is a `VehiclePassPage`, not `MigrationPage`;
- dashboard `Новый пропуск ТС` opens it;
- `--self-test` returns 0 with in-memory settings and injected/no-output service dependencies;
- production `pass_generator.py` still imports `getpass_ui.app.App` and does not import `getpass_qt`.

- [ ] **Step 2: Confirm RED**

Run navigation and entrypoint tests.

- [ ] **Step 3: Implement integration**

Construction flow in `getpass_qt.app`:
`SettingsService` → `ThemeManager` → `VehiclePassService` → `VehiclePassViewModel` → `MainWindow`.

Self-test must not call `save_pdf()` or `print_passes()`.

- [ ] **Step 4: GREEN**

Run:
`python -m pytest tests/test_qt_navigation.py tests/test_qt_entrypoint.py tests/test_qt_vehicle_page.py -v`

- [ ] **Step 5: Commit**

Commit message: `feat: integrate vehicle workflow into Qt shell`

---

### Task 8: Full regression, Windows preview smoke, and documentation

**Files:**
- Modify: `README.md`
- Modify tests only if a missing regression is discovered; do not weaken existing assertions.

**Interfaces:**
- No new runtime interface; this task proves Phase 2 acceptance criteria.

- [ ] **Step 1: Update README**

Document that the Qt preview now has a functional vehicle-pass workflow for form entry, existing-renderer preview, PDF output, and printing, while employee/journals/operations remain migration placeholders and Tkinter remains production.

- [ ] **Step 2: Run full Linux CI-equivalent verification**

Commands:

```bash
flake8 pass_generator.py getpass_core getpass_ui getpass_app getpass_design getpass_qt tests tools --count --max-line-length=127 --show-source --statistics
flake8 pass_generator.py getpass_core getpass_ui getpass_app getpass_design getpass_qt tests tools --count --select=C901 --max-complexity=10 --statistics
xvfb-run -a --server-args="-screen 0 1920x1200x24" python -m pytest --cov --cov-fail-under=60 --cov-report=xml -v
python -m pip_audit -r requirements.txt
python -m bandit -r getpass_core getpass_ui getpass_app getpass_design getpass_qt -ll
```

Expected: all blocking gates green. Report Low Bandit findings separately; do not claim total zero if low findings remain.

- [ ] **Step 3: Verify renderer contract and production boundary explicitly**

Run:

```bash
python -m pytest tests/test_renderer_contract.py tests/test_qt_entrypoint.py tests/test_workflows.py -v
```

Expected: protected renderer file manifest unchanged; build/release workflows still target `pass_generator.py`.

- [ ] **Step 4: Verify Windows CI on the PR head**

Required successful steps:
- Windows pytest;
- source `python -m getpass_qt --self-test`;
- legacy `GET-Passes.exe` build + self-test;
- `GET-Passes-Qt-Preview.exe` build + self-test;
- Inno Setup build;
- install/self-test/uninstall legacy Setup.exe.

- [ ] **Step 5: Final review and PR readiness**

Review diff for forbidden files and architecture leaks. `getpass_app` must contain no `PySide6` imports; `getpass_qt/views/vehicle_pass.py` must contain no direct `sqlite3`, `getpass_core.render`, or `getpass_core.printing` calls. Mark the PR ready only after all final-head workflows succeed.

- [ ] **Step 6: Commit documentation if needed**

Commit message: `docs: document PySide6 vehicle workflow`
