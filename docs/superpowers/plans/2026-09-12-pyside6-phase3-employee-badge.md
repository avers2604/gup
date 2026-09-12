# PySide6 Phase 3 Employee Badge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the PySide6 `employee` migration placeholder with a real permanent-employee badge workflow that preserves the existing badge renderer, photo crop behavior, journal semantics, PDF/print formats, and Tkinter production fallback.

**Architecture:** Add immutable employee-badge state and orchestration to `getpass_app`, expose it through a focused MVVM-lite ViewModel, and implement a two-column PySide6 page using the shared `ImagePreview`. Reuse `getpass_core.crop.compute_crop_from_state`, existing renderer functions and `BADGE_JOURNAL`; Qt owns presentation and confirmations only, while application services own validation, rendering, warning lookup and durable output orchestration.

**Tech Stack:** Python 3.13/3.14, PySide6 6.11.x, Pillow, existing `getpass_core`, SQLite, pytest, pytest-qt.

**Spec:** `docs/superpowers/specs/2026-09-11-pyside6-v2-ui-design.md`

## Global Constraints

- Keep `pass_generator.py` as the production Tkinter entry point during Phase 3.
- Do not modify `getpass_core/render.py`, `getpass_core/blank.py`, `getpass_core/fonts.py`, `assets/`, `fonts/`, or `fronts/`; renderer-contract tests must remain green.
- Do not change SQLite schema or migrations.
- Reuse the GET palette from `getpass_design.tokens`; no independent Qt color constants.
- Preserve the badge visual contract by continuing to use `render_single_badge_image()`, `build_badge_a4_grid()` and `build_badge_a4_single()`.
- Preserve legacy print modes exactly: `card`, `a4_grid`, `a4_single`.
- Preserve duplicate warning by `tab_num` and blacklist warning by employee FIO, but confirmations belong to the Qt presentation layer.
- Preserve durable issuance semantics: prepare before output, confirm after success, cancel after failure.
- Reuse `getpass_core.crop.compute_crop_from_state` for 3:4 crop geometry; do not fork the crop math.
- Phase 3 must not migrate badge journal windows, employee registry, batch badges, export, production packaging, or release cutover.

---

## File Map

**Create**
- `getpass_app/models/employee_badge.py` — immutable badge form state, print mode and pure validation.
- `getpass_app/services/employee_badge_service.py` — roles/printers, warnings, preview, photo persistence, document composition and durable PDF/print output.
- `getpass_qt/viewmodels/employee_badge_viewmodel.py` — MVVM-lite editable state/signals.
- `getpass_qt/widgets/photo_crop_dialog.py` — Qt crop shell backed by existing core crop geometry.
- `getpass_qt/views/employee_badge.py` — Variant-A employee badge page.
- `tests/test_employee_badge_model.py`
- `tests/test_employee_badge_service.py`
- `tests/test_qt_employee_badge_viewmodel.py`
- `tests/test_qt_photo_crop_dialog.py`
- `tests/test_qt_employee_badge_page.py`

**Modify**
- `getpass_qt/main_window.py` — replace only `employee` migration page with `EmployeeBadgePage`.
- `getpass_qt/app.py` — construct/inject employee service/ViewModel and extend safe `--self-test`.
- `getpass_qt/theme/stylesheet.py` — semantic badge/photo/crop styles using existing tokens.
- `tests/test_qt_navigation.py`, `tests/test_qt_entrypoint.py`, `tests/test_qt_theme.py` — Phase 3 contracts.
- `README.md` — document Phase 3 preview scope.

---

### Task 1: Employee-badge model and validation

**Files:**
- Create: `getpass_app/models/employee_badge.py`
- Test: `tests/test_employee_badge_model.py`

**Interfaces:**
- Produces `EmployeeBadgeData`, `EmployeeBadgeState`, `BadgeValidationIssue`.
- Produces `EmployeeBadgeData.to_renderer_dict(*, placeholder: bool = False) -> dict[str, object]`.
- Produces `validate_employee_badge(state: EmployeeBadgeState) -> tuple[BadgeValidationIssue, ...]`.

- [ ] **Step 1: Write failing tests**

```python
from getpass_app.models.employee_badge import (
    EmployeeBadgeData, EmployeeBadgeState, validate_employee_badge,
)


def test_renderer_contract_preserves_existing_badge_keys():
    data = EmployeeBadgeData(
        tab_num="01035", park='ОСП «Трамвайный парк № 5»', role="ВОДИТЕЛЬ",
        surname="ИВАНОВ", name="ИВАН", patronymic="ИВАНОВИЧ",
        phone="+79990000000", issue_date="12.09.2026",
        valid_until="12.09.2031", photo_path="photo.jpg",
    )
    result = data.to_renderer_dict()
    assert result["tab_num"] == "01035"
    assert result["fio"] == "ИВАНОВ И.И."
    assert result["photo_path"] == "photo.jpg"


def test_validation_requires_role_name_dates_and_photo():
    issues = validate_employee_badge(EmployeeBadgeState())
    fields = {issue.field for issue in issues}
    assert {"role", "surname", "name", "issue_date", "valid_until", "photo_path"} <= fields


def test_validation_rejects_valid_until_before_issue_date():
    state = EmployeeBadgeState(data=EmployeeBadgeData(
        role="ВОДИТЕЛЬ", surname="ИВАНОВ", name="ИВАН",
        issue_date="12.09.2026", valid_until="11.09.2026", photo_path="photo.jpg",
    ))
    assert any(issue.field == "valid_until" for issue in validate_employee_badge(state))
```

- [ ] **Step 2: Run RED**

Run: `pytest tests/test_employee_badge_model.py -v`
Expected: collection FAIL with `ModuleNotFoundError: getpass_app.models.employee_badge`.

- [ ] **Step 3: Implement immutable model**

Implement `EmployeeBadgeData` with the legacy fields and uppercase normalization only where already expected by the UI. Use `parse_date`, `format_date` and `split_fio` from `getpass_core.domain`; `EmployeeBadgeState.print_mode` is `Literal["card", "a4_grid", "a4_single"]` and defaults to `"card"`.

- [ ] **Step 4: Run GREEN**

Run: `pytest tests/test_employee_badge_model.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add getpass_app/models/employee_badge.py tests/test_employee_badge_model.py
git commit -m "feat: add employee badge application model"
```

---

### Task 2: Employee badge service, warnings and durable output

**Files:**
- Create: `getpass_app/services/employee_badge_service.py`
- Test: `tests/test_employee_badge_service.py`

**Interfaces:**
- Produces `EmployeeBadgeWarnings(duplicates: tuple[dict, ...], blacklist: tuple[dict, ...])`.
- Produces `EmployeeBadgeOutputError`.
- Produces `EmployeeBadgeService.roles()`, `printers()`, `warnings(state)`, `render_preview(data)`, `store_photo(cropped, tab_num)`, `build_document(state)`, `save_pdf(state, path)`, `print_badge(state, printer)`.

- [ ] **Step 1: Write failing service tests**

```python
def test_build_document_preserves_three_legacy_modes(service, valid_state):
    assert service.build_document(valid_state.replace(print_mode="card")).mode == "card"
    assert service.build_document(valid_state.replace(print_mode="a4_grid")).mode == "a4_grid"
    assert service.build_document(valid_state.replace(print_mode="a4_single")).mode == "a4_single"


def test_warnings_collect_duplicates_and_blacklist(service, valid_state):
    warnings = service.warnings(valid_state)
    assert warnings.duplicates[0]["tab_num"] == valid_state.data.tab_num
    assert warnings.blacklist[0]["incident"] == "test"


def test_save_pdf_uses_prepare_output_confirm_order(service, valid_state, events, tmp_path):
    service.save_pdf(valid_state, str(tmp_path / "badge.pdf"))
    assert events == ["prepare", "render", "save", "confirm"]


def test_save_pdf_cancels_prepared_issuance_on_output_error(service, valid_state, events, tmp_path):
    service._save_document = lambda *_: (_ for _ in ()).throw(OSError("disk"))
    with pytest.raises(EmployeeBadgeOutputError):
        service.save_pdf(valid_state, str(tmp_path / "badge.pdf"))
    assert events[-1] == "cancel"
```

- [ ] **Step 2: Run RED**

Run: `pytest tests/test_employee_badge_service.py -v`
Expected: FAIL because `EmployeeBadgeService` does not exist.

- [ ] **Step 3: Implement service with injected dependencies**

Use `BADGE_JOURNAL.find_duplicates(tab_num)`, `BADGE_JOURNAL.distinct("role")`, `blacklist.find(fio=...)`, `printing.get_available_printers`, `issuance.prepare/confirm/cancel`, and the three existing badge renderer functions. `store_photo()` writes a UUID JPEG under `config.PHOTO_DIR` at 300 DPI and never imports `getpass_ui`.

- [ ] **Step 4: Run GREEN and regression suite**

Run: `pytest tests/test_employee_badge_service.py tests/test_renderer_contract.py tests/test_issuance_recovery.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add getpass_app/services/employee_badge_service.py tests/test_employee_badge_service.py
git commit -m "feat: add employee badge application service"
```

---

### Task 3: Qt photo crop dialog using existing crop math

**Files:**
- Create: `getpass_qt/widgets/photo_crop_dialog.py`
- Test: `tests/test_qt_photo_crop_dialog.py`

**Interfaces:**
- Produces `PhotoCropDialog(QDialog)`.
- Constructor accepts a PIL `Image.Image`.
- `cropped_image() -> tuple[Image.Image, tuple[int, int, int, int]]` calls `compute_crop_from_state`.
- Wheel/buttons clamp zoom to `1.0..6.0`; mouse drag updates offsets.

- [ ] **Step 1: Write failing crop tests**

```python
def test_crop_dialog_uses_three_by_four_frame(qtbot, source_image):
    dialog = PhotoCropDialog(source_image)
    qtbot.addWidget(dialog)
    _, _, width, height = dialog.frame_box
    assert round(width / height, 3) == 0.75


def test_crop_dialog_delegates_final_crop_to_core(qtbot, source_image, monkeypatch):
    calls = []
    monkeypatch.setattr(crop_widget, "compute_crop_from_state", lambda *args: calls.append(args) or (source_image, (0, 0, 300, 400)))
    dialog = PhotoCropDialog(source_image)
    dialog.cropped_image()
    assert len(calls) == 1
```

- [ ] **Step 2: Run RED**

Run: `pytest tests/test_qt_photo_crop_dialog.py -v`
Expected: FAIL because widget module does not exist.

- [ ] **Step 3: Implement dialog**

Use `QPainter`/`QPixmap` only for display; retain the source PIL image and core crop state. Do not rasterize the final crop through Qt.

- [ ] **Step 4: Run GREEN**

Run: `pytest tests/test_qt_photo_crop_dialog.py tests/test_crop.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add getpass_qt/widgets/photo_crop_dialog.py tests/test_qt_photo_crop_dialog.py
git commit -m "feat: add Qt employee photo crop dialog"
```

---

### Task 4: Employee badge ViewModel

**Files:**
- Create: `getpass_qt/viewmodels/employee_badge_viewmodel.py`
- Test: `tests/test_qt_employee_badge_viewmodel.py`

**Interfaces:**
- Produces `EmployeeBadgeViewModel(QObject)` with `state_changed`, `preview_changed`, `validation_changed`, `busy_changed`, `operation_succeeded`, `operation_failed`.
- Produces `set_field(name, value)`, `set_print_mode(mode)`, `set_photo_path(path)`, `set_years(years)`, `roles()`, `printers()`, `warnings()`, `refresh_preview()`, `save_pdf(path)`, `print_badge(printer)`.

- [ ] **Step 1: Write failing ViewModel tests**

```python
def test_name_fields_are_normalized_to_uppercase(qtbot, viewmodel):
    viewmodel.set_field("surname", "Иванов")
    assert viewmodel.state.data.surname == "ИВАНОВ"


def test_plus_five_years_uses_issue_date(qtbot, viewmodel):
    viewmodel.set_field("issue_date", "12.09.2026")
    viewmodel.set_years(5)
    assert viewmodel.state.data.valid_until == "12.09.2031"


def test_preview_is_delegated_to_service(qtbot, viewmodel, service):
    viewmodel.refresh_preview()
    assert service.preview_calls == 1
```

- [ ] **Step 2: Run RED**

Run: `pytest tests/test_qt_employee_badge_viewmodel.py -v`
Expected: FAIL because ViewModel module does not exist.

- [ ] **Step 3: Implement minimal MVVM-lite state layer**

Keep dialogs, file pickers and blacklist/duplicate confirmation out of the ViewModel. It exposes warning data and output errors as signals only.

- [ ] **Step 4: Run GREEN**

Run: `pytest tests/test_qt_employee_badge_viewmodel.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add getpass_qt/viewmodels/employee_badge_viewmodel.py tests/test_qt_employee_badge_viewmodel.py
git commit -m "feat: add employee badge viewmodel"
```

---

### Task 5: Variant-A employee badge page

**Files:**
- Create: `getpass_qt/views/employee_badge.py`
- Test: `tests/test_qt_employee_badge_page.py`
- Modify: `getpass_qt/theme/stylesheet.py`
- Test: `tests/test_qt_theme.py`

**Interfaces:**
- Produces `EmployeeBadgePage(QWidget)` with left scrollable form and right sticky preview.
- Form fields: park, tab number, role, surname, name, patronymic, phone, issue date, valid-until date, photo selector/crop, print mode, printer.
- Primary action `Напечатать`; secondary `Сохранить PDF`.

- [ ] **Step 1: Write failing page tests**

```python
def test_employee_page_contains_operator_workflow(qtbot, viewmodel):
    page = EmployeeBadgePage(viewmodel, open_image=lambda: None)
    qtbot.addWidget(page)
    assert page.findChild(QLineEdit, "badge_surname") is not None
    assert page.findChild(QPushButton, "BadgePhotoButton") is not None
    assert page.findChild(ImagePreview, "BadgePreview") is not None
    assert page.findChild(QPushButton, "BadgePrintButton").text() == "Напечатать"


def test_badge_preview_is_debounced(qtbot, page, service):
    initial = service.preview_calls
    page.surname_edit.setText("И")
    page.surname_edit.setText("ИВ")
    page.surname_edit.setText("ИВА")
    assert service.preview_calls == initial
    qtbot.wait(180)
    assert service.preview_calls == initial + 1
```

- [ ] **Step 2: Run RED**

Run: `pytest tests/test_qt_employee_badge_page.py -v`
Expected: FAIL because page module does not exist.

- [ ] **Step 3: Implement page and semantic QSS**

Use the same 150 ms preview debounce as vehicle workflow. On output, query `viewmodel.warnings()` and use Qt confirmation dialogs before invoking PDF/print. Photo selection opens `PhotoCropDialog`, persists the returned PIL crop through the service/ViewModel, then refreshes preview.

- [ ] **Step 4: Run GREEN**

Run: `pytest tests/test_qt_employee_badge_page.py tests/test_qt_theme.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add getpass_qt/views/employee_badge.py getpass_qt/theme/stylesheet.py tests/test_qt_employee_badge_page.py tests/test_qt_theme.py
git commit -m "feat: add PySide6 employee badge page"
```

---

### Task 6: Shell integration, safe self-test and documentation

**Files:**
- Modify: `getpass_qt/main_window.py`
- Modify: `getpass_qt/app.py`
- Modify: `tests/test_qt_navigation.py`
- Modify: `tests/test_qt_entrypoint.py`
- Modify: `README.md`

**Interfaces:**
- `MainWindow(..., vehicle_viewmodel, employee_badge_viewmodel)` injects both workflows.
- `employee` route resolves to `EmployeeBadgePage`; other migration routes remain placeholders.
- `--self-test` exercises dashboard → employee → surname input → debounced badge preview, without save/print or persistent settings.

- [ ] **Step 1: Write failing integration tests**

```python
def test_employee_route_uses_real_employee_badge_page(window):
    window.sidebar.request_route("employee")
    assert window.active_route == "employee"
    assert window.stack.currentWidget() is window.employee_page


def test_self_test_exercises_employee_preview_after_debounce(monkeypatch):
    assert main(["--self-test"]) == 0
```

- [ ] **Step 2: Run RED**

Run: `pytest tests/test_qt_navigation.py tests/test_qt_entrypoint.py -v`
Expected: FAIL until injection and route replacement are implemented.

- [ ] **Step 3: Implement integration and docs**

Construct a real `EmployeeBadgeService` outside self-test and injected no-I/O dependencies inside self-test. README must say vehicle and employee workflows are real PySide6 previews while Tkinter remains production.

- [ ] **Step 4: Run GREEN**

Run: `pytest tests/test_qt_navigation.py tests/test_qt_entrypoint.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add getpass_qt/main_window.py getpass_qt/app.py tests/test_qt_navigation.py tests/test_qt_entrypoint.py README.md
git commit -m "feat: integrate employee badge workflow into Qt shell"
```

---

### Task 7: Final Phase 3 verification

**Files:** no functional changes unless a failing gate exposes a regression.

- [ ] **Step 1: Run strict Linux matrix**

Run the existing GitHub `Python application` workflow on Python 3.13 and 3.14. Expected: flake8 0, C901 0, full pytest PASS, dependency audit PASS, Bandit blocking levels PASS.

- [ ] **Step 2: Run Security workflow**

Expected: gitleaks PASS and CodeQL PASS.

- [ ] **Step 3: Run Windows PR smoke**

Expected: Windows pytest, source Qt self-test, legacy EXE build/self-test, Qt preview EXE build/self-test, Inno build and legacy install/self-test/uninstall all PASS.

- [ ] **Step 4: Review protected diff**

`git diff main...HEAD -- getpass_core/render.py getpass_core/blank.py getpass_core/fonts.py assets fonts fronts pass_generator.py .github installer`
Expected: no unintended renderer/production-cutover changes.

- [ ] **Step 5: Update PR from WIP to Ready for review only after all final-head workflows are green.**
