# PySide6 Phase 4 Blacklist and Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish Phase 4 by replacing the final `settings` migration placeholder with a real PySide6 operator-settings page that also provides model/view blacklist management, while applying persisted defaults to new Qt workflow state.

**Architecture:** Keep `getpass_core.blacklist` and `getpass_core.config` as the existing persistence implementations. Add UI-independent projections/services in `getpass_app`; extend current Qt ViewModels with explicit default application; expose settings and blacklist through one `SettingsPage` with two tabs so the nine-route shell remains aligned with the approved design. Views never call core storage directly.

**Tech Stack:** Python 3.13/3.14, PySide6 6.11.2, MVVM-lite, `QAbstractTableModel`/`QTableView`, existing JSON settings/blacklist persistence, pytest/pytest-qt, flake8/C901, pip-audit, Bandit, CodeQL, Windows PyInstaller/Inno smoke.

**Spec:** `docs/superpowers/specs/2026-09-11-pyside6-v2-ui-design.md`

## Global Constraints

- `getpass_core` remains Qt-independent and unchanged unless a proven parity bug requires a separate fix.
- Keep the existing nine-route shell; blacklist management lives inside the `settings` route rather than adding a tenth sidebar route.
- Settings persistence continues through `config.load_settings` / `config.save_settings`; unknown keys are not introduced.
- Do not expose draft/window geometry/paned-width implementation details as operator settings.
- Blacklist persistence continues through `getpass_core.blacklist`; preserve plate/FIO normalization and generated IDs/timestamps.
- Blacklist tables use Qt model/view rather than direct row-widget manipulation.
- Views do not call config, blacklist storage, SQLite, renderer, PDF or printer APIs directly.
- `pass_generator.py`, production PyInstaller/Inno workflow and release pipeline remain Tkinter until Phase 5.
- Qt self-test must not read or mutate production settings/blacklist files.

---

### Task 1: Application-layer settings and blacklist contracts

**Files:**
- Modify: `getpass_app/models/preferences.py`
- Modify: `getpass_app/services/settings_service.py`
- Create: `getpass_app/models/blacklist.py`
- Create: `getpass_app/services/blacklist_service.py`
- Test: `tests/test_settings_service.py`
- Create: `tests/test_blacklist_application.py`

**Interfaces:**
- Produces `OperatorDefaults` with persisted operator-facing defaults: `last_pass_num`, `territory`, `otb_post`, `otb_name`, `valid_until`, `is_temporary_car`, `print_mode`, `badge_park`, `badge_tab_num`, `badge_print_mode`, `auto_preview_target`, `warn_duplicates`, `print_pass_back`.
- Produces `SettingsService.load_operator_defaults() -> OperatorDefaults` and `save_operator_defaults(defaults) -> bool` while preserving unrelated existing config keys.
- Produces immutable `BlacklistEntry` and `BlacklistService.list_entries()`, `add_entry(...)`, `remove_entry(id)` wrapping the existing core module.

- [ ] **Step 1: Write failing application tests** for typed default loading/saving, invalid enum fallback, blacklist projections, validation (plate or FIO required; incident required), add/remove delegation and normalized results.
- [ ] **Step 2: Run CI and verify RED** reaches missing application APIs after strict lint/C901 passes.
- [ ] **Step 3: Implement minimal models/services** with dependency injection and no Qt imports.
- [ ] **Step 4: Run full Python matrix** and require lint/C901, pytest, audit and Bandit GREEN.
- [ ] **Step 5: Commit application-layer GREEN.**

### Task 2: Apply persisted defaults to existing Qt workflow state

**Files:**
- Modify: `getpass_qt/viewmodels/vehicle_pass_viewmodel.py`
- Modify: `getpass_qt/viewmodels/employee_badge_viewmodel.py`
- Modify: `getpass_qt/viewmodels/batch_viewmodel.py`
- Modify: `getpass_qt/app.py`
- Test: `tests/test_qt_vehicle_viewmodel.py`
- Test: `tests/test_qt_employee_badge_viewmodel.py`
- Test: `tests/test_qt_batch_viewmodel.py`
- Test: `tests/test_qt_entrypoint.py`

**Interfaces:**
- `VehiclePassViewModel(..., defaults: OperatorDefaults | None = None)` seeds pass number/territory/common validity/OTB/temporary/page format/back printing without altering lookup semantics.
- `EmployeeBadgeViewModel(..., defaults: OperatorDefaults | None = None)` seeds personnel number/park/print mode while retaining date behavior and post-issue preservation.
- `BatchViewModel(..., defaults: OperatorDefaults | None = None)` seeds vehicle/badge import defaults from the same projection.
- Normal app startup loads settings once through `SettingsService`; self-test uses synthetic defaults and never reads `settings.json`.

- [ ] **Step 1: Write failing ViewModel/entrypoint tests** proving persisted defaults seed new state and self-test remains file-independent.
- [ ] **Step 2: Verify RED** is caused only by missing defaults constructor/wiring behavior.
- [ ] **Step 3: Implement minimal constructor/wiring changes**; keep all existing call sites backward-compatible with `defaults=None`.
- [ ] **Step 4: Run full Python matrix GREEN.**
- [ ] **Step 5: Commit defaults wiring.**

### Task 3: Blacklist model/view and settings ViewModel

**Files:**
- Create: `getpass_qt/models/blacklist_table_model.py`
- Create: `getpass_qt/viewmodels/blacklist_viewmodel.py`
- Create: `getpass_qt/viewmodels/settings_viewmodel.py`
- Test: `tests/test_qt_blacklist_table_model.py`
- Test: `tests/test_qt_blacklist_viewmodel.py`
- Create: `tests/test_qt_settings_viewmodel.py`

**Interfaces:**
- `BlacklistTableModel` exposes columns `Госномер`, `ФИО`, `Инцидент`, `Дата` plus an ID role for actions.
- `BlacklistViewModel` owns immutable entries, refresh/add/remove commands and error/state signals; no direct core calls from widgets.
- `SettingsViewModel` owns an editable `OperatorDefaults` projection, validates supported print modes/preview target and persists through `SettingsService`.

- [ ] **Step 1: Write RED model/ViewModel tests.**
- [ ] **Step 2: Verify RED after lint/C901.**
- [ ] **Step 3: Implement Qt model and explicit-signal ViewModels.**
- [ ] **Step 4: Run full Python matrix GREEN.**
- [ ] **Step 5: Commit model/ViewModel layer.**

### Task 4: Real SettingsPage with blacklist tab and shell integration

**Files:**
- Create: `getpass_qt/views/settings.py`
- Modify: `getpass_qt/main_window.py`
- Modify: `getpass_qt/app.py`
- Modify: `tests/test_qt_navigation.py`
- Modify: `tests/test_qt_entrypoint.py`
- Create: `tests/test_qt_settings_page.py`

**Interfaces:**
- `SettingsPage(settings_viewmodel, blacklist_viewmodel)` contains `QTabWidget` tabs `Параметры` and `Черный список`.
- Parameters tab edits only `OperatorDefaults`; save status is explicit and notes defaults apply to newly created form state / next application start rather than silently mutating an in-progress document.
- Blacklist tab uses `QTableView`, plate/FIO/incident inputs, add/remove actions and selection-driven removal.
- `settings` joins `_REAL_ROUTES`; shell stack remains 9.
- Self-test constructs fake services, visits `settings`, and performs no production settings/blacklist I/O.

- [ ] **Step 1: Write failing page/navigation/self-test tests.**
- [ ] **Step 2: Verify RED** on missing page/wiring only.
- [ ] **Step 3: Implement page and route wiring.**
- [ ] **Step 4: Run full Python matrix GREEN.**
- [ ] **Step 5: Commit UI integration.**

### Task 5: Phase 4 completion docs and final verification

**Files:**
- Modify: `README.md`
- Review only: `pass_generator.py`, `.github/workflows/*`, `getpass_core/*`

- [ ] **Step 1: Update README** so all nine PySide6 routes are real, blacklist management is documented inside Settings, and Phase 4 is described as code-complete while production remains Tkinter.
- [ ] **Step 2: Compare branch with its Phase 4 base** and prove protected files/workflows were not changed.
- [ ] **Step 3: Run final Python 3.13/3.14 gates**: strict flake8/C901, full pytest + coverage, pip-audit, Bandit.
- [ ] **Step 4: Require Security GREEN**: gitleaks + CodeQL.
- [ ] **Step 5: Require Windows PR smoke GREEN**: Windows tests, source Qt self-test, production EXE build/self-test, Qt preview EXE build/self-test, Inno build, install/self-test/uninstall.
- [ ] **Step 6: Audit PR comments/review threads, update PR description and mark ready for review.**

After this PR is review-ready, Phase 4 implementation is code-complete. Phase 5 production cutover must remain a separate PR/plan and must not begin by changing `pass_generator.py` until the Phase 4 stack is accepted/merged.
