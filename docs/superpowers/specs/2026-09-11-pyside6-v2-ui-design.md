# GET-Passes 2.0 — PySide6 UI Architecture Design

## Status

Approved direction for implementation planning.

This design replaces the earlier exploratory recommendation in `docs/PYSIDE6_MIGRATION.md` and defines the target architecture for GET-Passes 2.0.

## Goals

Migrate the presentation layer from Tkinter to PySide6 while preserving the existing business behavior, SQLite data, printing flow and document renderer.

The new UI must implement the previously selected minimalist operator-first concept (variant A): fast navigation, a persistent left sidebar, clear primary actions, a large live preview and minimal visual competition from secondary operations.

The migration must not change the visual appearance of vehicle passes or employee passes. Existing renderer output is treated as a compatibility contract.

## Non-goals

- Do not redesign printed passes, badges, backs, PDFs or their typography/coordinates.
- Do not replace SQLite.
- Do not introduce a web frontend, browser shell, Electron, Tauri, REST API or microservices.
- Do not rewrite working core services solely to match a textbook architecture.
- Do not remove the Tkinter UI until the PySide6 application has passed Windows packaging and physical acceptance.
- Do not use self-signed signing as a substitute for public Authenticode trust; signing remains a separate release concern.

## Technology

- Python: keep the repository constraint `>=3.13,<3.15`.
- UI: PySide6 `>=6.11,<6.12`.
- Architecture: MVVM-lite.
- Persistence: existing SQLite storage and migrations.
- Rendering: existing Pillow-based `getpass_core.render` / related renderer modules.
- PDF/printing: existing core implementation.
- Packaging: existing PyInstaller + Inno Setup flow, adapted to include PySide6 runtime/plugins.

## Global compatibility constraints

1. Existing SQLite databases must open without manual conversion.
2. Existing migrations remain authoritative.
3. Existing journal and issuance records remain readable.
4. `getpass_core` remains importable without importing PySide6.
5. Renderer inputs and outputs remain compatible with the current application.
6. Vehicle-pass autocomplete must continue to reuse only vehicle characteristics and must not restore driver personal data from historical passes.
7. Legacy vehicle drafts must remain suppressed.
8. `Ctrl+S` and `Ctrl+P` remain supported for save/print actions.
9. Light and dark themes must derive from the existing GET design tokens rather than new ad-hoc colors.

## Architectural boundaries

### 1. Core

`getpass_core/` remains the stable domain/infrastructure foundation. It owns existing renderer, storage, migrations, printing, issuance, backup, blacklist, encryption and other low-level behavior.

The migration may make narrow refactors to expose reusable functions, but core code must not depend on Qt classes, `QObject`, widgets or signals.

### 2. Application layer

Create `getpass_app/` as the UI-independent orchestration layer.

Proposed structure:

```text
getpass_app/
├── models/
│   ├── vehicle_pass.py
│   ├── employee_pass.py
│   └── operation.py
├── services/
│   ├── vehicle_pass_service.py
│   ├── employee_pass_service.py
│   ├── journal_service.py
│   ├── printing_service.py
│   └── settings_service.py
└── validation/
    ├── vehicle.py
    └── employee.py
```

This layer owns complete user-level use cases such as:

- look up known vehicle characteristics;
- validate a vehicle pass;
- check blacklist and duplicate conditions;
- generate preview input;
- save a pass PDF;
- print a pass;
- commit issuance/journal changes;
- generate/print employee passes;
- expose journal queries without returning widgets.

Services may wrap existing `getpass_core` functions rather than duplicate them.

### 3. PySide6 presentation layer

Create `getpass_qt/`.

```text
getpass_qt/
├── app.py
├── main_window.py
├── viewmodels/
│   ├── main_viewmodel.py
│   ├── vehicle_pass_viewmodel.py
│   ├── employee_pass_viewmodel.py
│   └── journal_viewmodel.py
├── views/
│   ├── dashboard.py
│   ├── vehicle_pass.py
│   ├── employee_pass.py
│   ├── journal.py
│   └── settings.py
├── widgets/
│   ├── sidebar.py
│   ├── field.py
│   ├── card.py
│   ├── preview.py
│   ├── status_chip.py
│   └── action_bar.py
├── theme/
│   ├── tokens.py
│   ├── stylesheet.py
│   └── manager.py
└── resources/
    └── icons/
```

Views own layout and user interaction only. ViewModels expose state, commands and Qt signals. Application services perform business operations.

## MVVM-lite rules

Use Qt signals only at the presentation boundary. Do not spread `QObject` into `getpass_core` or `getpass_app`.

A ViewModel may:

- hold editable screen state;
- expose signals such as `changed`, `validation_changed`, `preview_changed`, `busy_changed` and `error_raised`;
- translate user actions into application-service calls;
- convert Pillow images to UI-ready preview values through a presentation adapter.

A View must not directly call SQLite, journals, blacklist storage, renderer, PDF writer or printer APIs.

Avoid an over-engineered binding framework. Explicit signal/slot wiring is preferred.

## Main window design

The new window uses a fixed application shell:

```text
┌─────────────────┬──────────────────────────────────────────────┐
│       ГЭТ       │ Current section                 status/theme │
│                 ├────────────────────────┬─────────────────────┤
│ Главная         │                        │                     │
│ Пропуск ТС      │      WORK AREA         │      PREVIEW        │
│ Работник        │                        │                     │
│ ─────────────   │                        │                     │
│ Журналы         │                        │                     │
│ Незавершённые   │                        │                     │
│ Резервные копии │                        │                     │
│                 ├────────────────────────┴─────────────────────┤
│ Диагностика     │      secondary action     PRIMARY ACTION    │
│ Настройки       │                                              │
└─────────────────┴──────────────────────────────────────────────┘
```

Use `QStackedWidget` for main page switching. Pages remain alive while the operator moves between sections unless a page explicitly releases large preview resources.

The sidebar is persistent and visually indicates the active section.

## Dashboard

The dashboard is an operator launch surface, not an analytics product.

Primary cards:

- New vehicle pass;
- Employee pass;
- Batch printing.

Secondary content:

- recent operations;
- quick links to journals and unfinished operations;
- printer/system readiness summary.

Avoid vanity charts and statistics that do not change operator decisions.

## Vehicle pass page

The vehicle pass page retains all current functional fields but reorganizes them into a clearer task sequence.

Left/work column:

1. pass 1 / pass 2 selector;
2. blank number;
3. registration plate;
4. brand/model/type/color;
5. driver position/FIO/phone;
6. access zone;
7. issue/validity and OTB details;
8. collapsible print options.

Right column:

- live preview rendered by the existing renderer;
- pass 1/pass 2 target selector;
- open-large action;
- front/back selection when applicable.

Bottom action bar:

- secondary: Save PDF;
- primary: Print.

Mass printing, registry, export and journal actions move out of the primary issuance flow and remain accessible through navigation or secondary menus.

The A4/A5 behavior remains unchanged. A5 disables pass 2 at the ViewModel/application level as well as visually.

## Employee pass page

Use the same two-column pattern as the vehicle page.

Left/work column:

1. unit and personnel number;
2. position and employee name;
3. phone;
4. photo selection/cropping;
5. validity period;
6. collapsible print options.

Right column:

- existing employee-pass preview;
- open-large action.

The printed employee pass remains visually unchanged.

Photo cropping can initially reuse the current core crop logic, with a new Qt crop dialog at the presentation layer.

## Preview contract

Renderer output must remain independent from Qt.

Preview flow:

```text
ViewModel data
  -> application service
  -> existing renderer
  -> PIL.Image
  -> Qt adapter (ImageQt/QImage/QPixmap)
  -> PreviewWidget
```

`PreviewWidget` may scale, fit and zoom the image for display but must not draw, recolor or modify document content.

Regression coverage must detect unintended renderer changes. Representative fixtures for vehicle and employee passes should compare output dimensions and stable reference images/hashes where deterministic.

## Design system

The existing brand tokens are authoritative.

Required base colors:

- navy `#24305E`;
- teal `#009CBC`;
- red `#E4032E`;
- yellow `#FBBA00`;
- lime `#AFCB37`;
- mint `#8ACBC1`;
- grey `#DADADA`.

Existing light/dark semantic roles remain the source for ground, surface, text, lines, actions, focus and statuses.

Do not hard-code arbitrary visual colors in individual views. QSS is generated from semantic theme tokens.

Reusable Qt components should cover at least:

- SidebarItem;
- SectionHeader;
- Card;
- FormField;
- StatusChip;
- PreviewWidget;
- Primary/Secondary/Danger buttons;
- ActionBar.

Use local deterministic vector/raster icons, not emoji, as primary navigation icons.

## Accessibility and keyboard use

- Logical tab order on all issuance forms.
- Visible focus state using the existing focus/accent token.
- `Ctrl+S` and `Ctrl+P` preserved.
- Labels associated with their input controls.
- Buttons have accessible names independent of icons.
- Do not encode validation/status only by color.
- Main operator actions remain reachable without a mouse.

## Responsiveness and DPI

Target Windows desktop resolutions/scales:

- 1366x768 at 100%;
- 1920x1080 at 100%, 125% and 150%;
- 4K/200% scaling.

At constrained width, preview area shrinks before core form controls disappear. The primary action bar must remain visible. Scroll only the form content, not the entire application shell.

Qt high-DPI behavior is used rather than porting Tk-specific DPI helpers into the new UI.

## Concurrency

The GUI thread must not execute long blocking tasks.

Use `QThreadPool`/`QRunnable` for:

- large PDF generation;
- batch operations;
- backups;
- import/export;
- blocking print preparation when needed.

Workers return plain data/results. Widgets are updated only on the GUI thread through signals.

Fast operations such as field validation and simple SQLite lookups may remain synchronous if measured latency is negligible.

## Error handling

Application services return/raise domain-meaningful errors. ViewModels translate them into UI state or dialogs.

Use modal dialogs only when the operator must make a decision or cannot continue. Non-blocking success/status feedback should use status chips/toasts/status area rather than repeated informational message boxes.

Destructive actions such as clearing entered data, deleting blacklist records or restoring backups continue to require explicit confirmation.

## Migration strategy

The migration is incremental and keeps the current Tkinter application usable until cutover.

### Phase 1 — foundation

- add PySide6 dependency and packaging support;
- create `getpass_app` application layer skeleton and tests;
- create `getpass_qt` shell, theme and sidebar;
- keep `pass_generator.py` launching Tkinter by default;
- add a development entry point for Qt.

### Phase 2 — vehicle passes

- move vehicle issuance orchestration out of Tkinter `App` into application services;
- implement vehicle ViewModel and page;
- use the unchanged renderer;
- prove A4/A5, pass 1/pass 2, PDF and print parity.

### Phase 3 — employee passes

- move employee issuance orchestration to application services;
- implement employee ViewModel/page and Qt photo workflow;
- prove PDF/print parity.

### Phase 4 — journals and operations

- migrate journals, blacklist, unfinished operations, batch printing, backup/restore and diagnostics;
- use Qt model/view classes for tables rather than direct widget row manipulation.

### Phase 5 — production cutover

- switch `pass_generator.py` to Qt;
- retain a temporary legacy Tkinter entry point for rollback/testing;
- update PyInstaller/Inno setup and Windows smoke tests;
- complete physical workstation/printer acceptance.

### Phase 6 — cleanup

Remove legacy Tkinter presentation code only after:

- all required workflows exist in Qt;
- Windows package smoke passes;
- existing databases open successfully;
- printer acceptance passes;
- renderer parity tests pass;
- no rollback to Tkinter is required.

## Testing strategy

### Core/application tests

Application services are tested without creating a `QApplication` wherever possible.

Tests cover:

- vehicle validation;
- employee validation;
- vehicle cache lookup behavior;
- no historical driver-data autofill;
- duplicate/blacklist decision paths;
- issuance/journal writes;
- save/print orchestration;
- settings compatibility.

### ViewModel tests

Instantiate ViewModels with fake services. Verify state transitions and emitted signals for success, validation errors and service failures.

### Qt widget tests

Use headless/offscreen Qt in CI where practical. Cover:

- navigation and stacked-page switching;
- primary controls present and enabled correctly;
- A4/A5 pass-2 state;
- keyboard shortcuts;
- theme application;
- basic focus/tab order.

### Renderer parity

Before substantial UI migration, create regression fixtures from the current renderer. New Qt code must feed equivalent renderer data and produce the same document output for those fixtures.

### Windows packaging

Existing Windows smoke remains mandatory and is extended to launch the Qt executable with an application self-test. PyInstaller must include required Qt platform/image plugins. Inno Setup install/self-test/uninstall remains part of CI.

## Release strategy

Treat the cutover as GET-Passes 2.0 because the presentation architecture changes materially even though data and printed documents remain compatible.

Do not create a production 2.0 tag until:

- Qt migration phases required for daily operation are complete;
- all CI is green;
- Windows installation smoke passes;
- real printer/workstation acceptance passes;
- signing policy for the chosen release channel is satisfied.

## Acceptance criteria

The migration is complete when all of the following are true:

1. Default application entry point uses PySide6.
2. Daily operator workflows no longer require Tkinter.
3. Existing SQLite data works without manual conversion.
4. Vehicle and employee document renderer output remains unchanged for regression fixtures.
5. Main navigation follows the selected minimalist variant A.
6. Light/dark themes use existing GET design tokens.
7. Vehicle and employee forms provide live preview using the existing renderer.
8. Print/PDF/batch/journal/backup workflows are available.
9. `Ctrl+S` and `Ctrl+P` work in the relevant pages.
10. Windows CI builds, installs, self-tests and uninstalls the Qt package successfully.
11. Physical printer/workstation acceptance is completed before production cutover.

## Explicit implementation principles

- Preserve behavior first; improve presentation second.
- Prefer adapters around proven core code to rewrites.
- Keep ViewModels testable and relatively small.
- Keep Qt out of core/application code.
- Avoid generic enterprise abstractions unless at least two real consumers need them.
- Every migration phase must leave a runnable application and must be independently reviewable.
