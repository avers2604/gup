# GET-Passes 2.0 PySide6 Phase 1 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a testable PySide6 application shell and UI-independent application boundary alongside the existing Tkinter application without changing the default production entry point, SQLite data, printed pass appearance, renderer behavior, or current production packaging.

**Architecture:** Phase 1 introduces three narrow foundations: a renderer-contract guard, a UI-independent `getpass_app` package, and a PySide6 `getpass_qt` shell using MVVM-lite. Existing brand tokens are moved to a presentation-neutral package and re-exported to Tkinter for compatibility. The current `pass_generator.py` remains the production Tkinter entry point; Qt is launched through `python -m getpass_qt` and is packaged only as a CI preview executable until later migration phases.

**Tech Stack:** Python 3.13/3.14, PySide6 6.11.x, Pillow 12.x, SQLite through existing `getpass_core`, pytest, pytest-qt, PyInstaller 6.22.2, GitHub Actions Windows/Linux.

**Spec:** `docs/superpowers/specs/2026-09-11-pyside6-v2-ui-design.md`

## Global Constraints

- Keep Python requirement exactly `>=3.13,<3.15`.
- Runtime PySide6 constraint is `>=6.11,<6.12`; `requirements.txt` pins the concrete tested wheel `PySide6==6.11.2`.
- Keep `pyproject.toml` project version at `1.1.0` during Phase 1; version `2.0.0` is reserved for production cutover.
- `pass_generator.py` continues to start the existing Tkinter application by default in Phase 1.
- Do not alter SQLite schema, migration versions, journal formats, issuance semantics, printer behavior, or user data locations.
- Do not alter printed vehicle passes, employee passes, backs, typography, coordinates, renderer algorithms, renderer assets, or renderer fonts.
- Preserve the regression from PR #42: vehicle autocomplete reuses only brand/model/type/color; old driver data and legacy vehicle drafts must not return.
- Existing GET colors remain authoritative: navy `#24305E`, teal `#009CBC`, red `#E4032E`, yellow `#FBBA00`, lime `#AFCB37`, mint `#8ACBC1`, grey `#DADADA`.
- Qt must not be imported by `getpass_core` or `getpass_app`.
- Qt tests run headlessly using `QT_QPA_PLATFORM=offscreen`; existing Tkinter tests continue to use Xvfb on Linux.
- Production `.github/workflows/build-exe.yml` and `.github/workflows/release.yml` remain on the Tkinter entry point in Phase 1. Qt packaging is proven only in the PR smoke workflow through a separate preview executable.

---

## File Structure for Phase 1

### Create

- `getpass_design/__init__.py` — presentation-neutral export surface for design tokens.
- `getpass_design/tokens.py` — existing GET brand palettes, spacing, radii and typography moved without value changes.
- `getpass_app/__init__.py` — application-layer package marker.
- `getpass_app/models/__init__.py`
- `getpass_app/models/preferences.py` — immutable UI preference model used by both current/future presentation layers.
- `getpass_app/services/__init__.py`
- `getpass_app/services/settings_service.py` — UI-independent adapter around `getpass_core.config` settings.
- `getpass_qt/__init__.py`
- `getpass_qt/__main__.py` — development/CI Qt entry point.
- `getpass_qt/app.py` — QApplication bootstrap and Qt self-test.
- `getpass_qt/main_window.py` — fixed shell with sidebar and stacked pages.
- `getpass_qt/viewmodels/__init__.py`
- `getpass_qt/viewmodels/main_viewmodel.py` — active route state and route validation.
- `getpass_qt/views/__init__.py`
- `getpass_qt/views/dashboard.py` — operator launch page for Phase 1.
- `getpass_qt/views/migration_page.py` — explicit page shown for workflows not yet migrated.
- `getpass_qt/widgets/__init__.py`
- `getpass_qt/widgets/sidebar.py` — persistent sidebar with text navigation.
- `getpass_qt/theme/__init__.py`
- `getpass_qt/theme/stylesheet.py` — QSS generator from semantic GET tokens.
- `getpass_qt/theme/manager.py` — theme application/toggle/persistence.
- `tools/update_renderer_contract.py` — deterministic manifest generator for renderer code/assets.
- `tests/fixtures/renderer_contract.json` — generated SHA-256 manifest of renderer-affecting files.
- `tests/test_renderer_contract.py`
- `tests/test_design_tokens.py`
- `tests/test_settings_service.py`
- `tests/test_qt_theme.py`
- `tests/test_qt_navigation.py`
- `tests/test_qt_entrypoint.py`

### Modify

- `getpass_ui/tokens.py` — compatibility re-export from `getpass_design.tokens`; no semantic/value changes.
- `pyproject.toml` — add PySide6 dependency and include new packages in coverage source list.
- `requirements.txt` — add pinned PySide6 runtime dependency.
- `requirements-dev.txt` — add pytest-qt.
- `tests/conftest.py` — select offscreen Qt platform before PySide6 import while preserving current Tk fixtures.
- `.github/workflows/python-app.yml` — lint/test/audit new packages under offscreen Qt.
- `.github/workflows/windows-ci.yml` — run Qt source self-test and build/run a CI-only Qt preview EXE.
- `README.md` — document the Phase 1 developer preview command and state that production still launches Tkinter.

### Explicitly do not modify in Phase 1

- `pass_generator.py`
- `getpass_core/render.py`
- `getpass_core/blank.py`
- `getpass_core/fonts.py`
- SQLite migration/storage schema files
- `.github/workflows/build-exe.yml`
- `.github/workflows/release.yml`
- `installer/GET-Passes.iss`

---

### Task 1: Freeze the Printed-Document Contract Before Qt Work

**Files:**
- Create: `tools/update_renderer_contract.py`
- Create: `tests/fixtures/renderer_contract.json`
- Create: `tests/test_renderer_contract.py`
- Existing protected inputs: `getpass_core/render.py`, `getpass_core/blank.py`, `getpass_core/fonts.py`, `assets/**`, `fonts/**`, `fronts/**`

**Interfaces:**
- Consumes: repository paths only; no application imports are required to calculate hashes.
- Produces: `tests/fixtures/renderer_contract.json`, a sorted mapping `{relative_path: sha256_hex}` used as a deliberate change gate for anything capable of changing printed appearance.

- [ ] **Step 1: Write the failing renderer-contract test**

Create `tests/test_renderer_contract.py`:

```python
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests" / "fixtures" / "renderer_contract.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_renderer_contract_files_are_unchanged():
    expected = json.loads(MANIFEST.read_text(encoding="utf-8"))
    actual = {name: _sha256(ROOT / name) for name in expected}
    assert actual == expected
```

This must fail initially because the manifest does not exist.

- [ ] **Step 2: Run the new test and confirm RED**

Run:

```bash
python -m pytest tests/test_renderer_contract.py -v
```

Expected: FAIL with `FileNotFoundError` for `tests/fixtures/renderer_contract.json`.

- [ ] **Step 3: Add the manifest generator**

Create `tools/update_renderer_contract.py`:

```python
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "tests" / "fixtures" / "renderer_contract.json"
PROTECTED_FILES = (
    ROOT / "getpass_core" / "render.py",
    ROOT / "getpass_core" / "blank.py",
    ROOT / "getpass_core" / "fonts.py",
)
PROTECTED_DIRS = (
    ROOT / "assets",
    ROOT / "fonts",
    ROOT / "fronts",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    files = list(PROTECTED_FILES)
    for directory in PROTECTED_DIRS:
        if directory.exists():
            files.extend(path for path in directory.rglob("*") if path.is_file())
    payload = {
        path.relative_to(ROOT).as_posix(): _sha256(path)
        for path in sorted(set(files))
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Capture the baseline from the approved current renderer**

Run:

```bash
python tools/update_renderer_contract.py
python -m pytest tests/test_renderer_contract.py tests/test_render.py -v
```

Expected: PASS. The manifest must contain `getpass_core/render.py`, `getpass_core/blank.py`, and `getpass_core/fonts.py` plus all current files under `assets/`, `fonts/`, and `fronts/`.

- [ ] **Step 5: Commit the contract before any PySide6 implementation**

```bash
git add tools/update_renderer_contract.py tests/fixtures/renderer_contract.json tests/test_renderer_contract.py
git commit -m "test: freeze printed document renderer contract"
```

Reviewer rule: any later manifest change requires an explicit reason tied to an approved printed-document change; Phase 1 must not regenerate it.

---

### Task 2: Add the PySide6 Runtime and Headless Test Harness

**Files:**
- Modify: `pyproject.toml`
- Modify: `requirements.txt`
- Modify: `requirements-dev.txt`
- Modify: `tests/conftest.py`
- Create: `tests/test_qt_dependency.py`

**Interfaces:**
- Consumes: current Python constraint `>=3.13,<3.15`.
- Produces: importable PySide6 6.11.x runtime and `qtbot` support; does not alter the production entry point.

- [ ] **Step 1: Write the failing dependency/version test**

Create `tests/test_qt_dependency.py`:

```python
from PySide6.QtCore import qVersion


def test_qt_runtime_is_supported_611_line():
    major, minor, *_ = (int(part) for part in qVersion().split("."))
    assert (major, minor) == (6, 11)
```

- [ ] **Step 2: Verify RED before adding the dependency**

In a clean environment based on the current requirements:

```bash
python -m pytest tests/test_qt_dependency.py -v
```

Expected: collection/import failure `ModuleNotFoundError: No module named 'PySide6'`.

- [ ] **Step 3: Add runtime and test dependencies**

Update `pyproject.toml` dependencies to:

```toml
dependencies = [
  "Pillow>=12.0,<13",
  "cryptography>=50,<51",
  "PySide6>=6.11,<6.12",
]
```

Keep `version = "1.1.0"`.

Update `requirements.txt` runtime section to include:

```text
Pillow==12.3.0
cryptography==50.0.1
PySide6==6.11.2
```

Update `requirements-dev.txt` to add:

```text
pytest-qt>=4.5,<5
```

- [ ] **Step 4: Force Qt offscreen mode before tests import PySide6**

At the top of `tests/conftest.py`, before any PySide6 import, add:

```python
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
```

Do not remove or rewrite existing Tkinter fixtures.

- [ ] **Step 5: Install and prove GREEN on both GUI stacks**

Run:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests/test_qt_dependency.py tests/test_render.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit dependencies separately**

```bash
git add pyproject.toml requirements.txt requirements-dev.txt tests/conftest.py tests/test_qt_dependency.py
git commit -m "build: add PySide6 foundation dependencies"
```

---

### Task 3: Extract GET Design Tokens Without Changing Any Values

**Files:**
- Create: `getpass_design/__init__.py`
- Create: `getpass_design/tokens.py`
- Modify: `getpass_ui/tokens.py`
- Create: `tests/test_design_tokens.py`

**Interfaces:**
- Consumes: every public token/helper currently defined by `getpass_ui.tokens`.
- Produces: presentation-neutral `getpass_design.tokens`; legacy imports from `getpass_ui.tokens` remain compatible and refer to the same objects/functions.

- [ ] **Step 1: Write compatibility tests before moving tokens**

Create `tests/test_design_tokens.py`:

```python
from getpass_design import tokens as shared
from getpass_ui import tokens as legacy


def test_get_brand_colors_are_unchanged():
    assert shared.BRAND == {
        "navy": "#24305E",
        "teal": "#009CBC",
        "red": "#E4032E",
        "yellow": "#FBBA00",
        "lime": "#AFCB37",
        "mint": "#8ACBC1",
        "grey": "#DADADA",
    }


def test_legacy_tk_tokens_reexport_shared_objects():
    assert legacy.BRAND is shared.BRAND
    assert legacy.LIGHT is shared.LIGHT
    assert legacy.DARK is shared.DARK
    assert legacy.PALETTES is shared.PALETTES
    assert legacy.SPACE is shared.SPACE
    assert legacy.RADIUS is shared.RADIUS
    assert legacy.TYPE is shared.TYPE
```

- [ ] **Step 2: Verify RED**

```bash
python -m pytest tests/test_design_tokens.py -v
```

Expected: FAIL because `getpass_design` does not exist.

- [ ] **Step 3: Move the current token implementation byte-for-byte in semantics**

Copy the current implementation from `getpass_ui/tokens.py` to `getpass_design/tokens.py` without changing any color, palette role, spacing value, radius, typography role, helper algorithm, or font stack.

Create `getpass_design/__init__.py`:

```python
"""Shared GET visual design primitives."""
```

Replace `getpass_ui/tokens.py` with an explicit compatibility re-export:

```python
"""Compatibility exports for the legacy Tkinter presentation layer."""
from getpass_design.tokens import (
    BRAND, DARK, FONT_STACK, LIGHT, PALETTES, RADIUS, SPACE, TRANSPORT, TYPE,
    Palette, contrast_ratio, darken, lighten, mix, readable_on,
    relative_luminance,
)

__all__ = [
    "BRAND", "DARK", "FONT_STACK", "LIGHT", "PALETTES", "RADIUS", "SPACE",
    "TRANSPORT", "TYPE", "Palette", "contrast_ratio", "darken", "lighten",
    "mix", "readable_on", "relative_luminance",
]
```

- [ ] **Step 4: Prove token compatibility and legacy theme health**

Run:

```bash
python -m pytest tests/test_design_tokens.py tests/test_theme.py -v
```

If the repository has no `tests/test_theme.py`, run all tests matching theme/tokens plus the full suite:

```bash
python -m pytest -q
```

Expected: PASS with no renderer-contract manifest changes.

- [ ] **Step 5: Commit the neutral design package**

```bash
git add getpass_design getpass_ui/tokens.py tests/test_design_tokens.py
git commit -m "refactor: share GET design tokens across UI stacks"
```

---

### Task 4: Add a UI-Independent Settings Boundary

**Files:**
- Create: `getpass_app/__init__.py`
- Create: `getpass_app/models/__init__.py`
- Create: `getpass_app/models/preferences.py`
- Create: `getpass_app/services/__init__.py`
- Create: `getpass_app/services/settings_service.py`
- Create: `tests/test_settings_service.py`

**Interfaces:**
- Consumes: `getpass_core.config.load_settings() -> dict`, `getpass_core.config.save_settings(values: dict) -> bool`.
- Produces: `UiPreferences(theme: Literal["light", "dark"])`, `SettingsService.load_ui_preferences() -> UiPreferences`, `SettingsService.save_theme(theme: str) -> bool`.

- [ ] **Step 1: Write service tests with injected fake storage**

Create `tests/test_settings_service.py`:

```python
import pytest

from getpass_app.models.preferences import UiPreferences
from getpass_app.services.settings_service import SettingsService


def test_load_ui_preferences_accepts_dark():
    service = SettingsService(
        load=lambda: {"theme": "dark"},
        save=lambda values: True,
    )
    assert service.load_ui_preferences() == UiPreferences(theme="dark")


def test_load_ui_preferences_normalizes_unknown_theme_to_light():
    service = SettingsService(
        load=lambda: {"theme": "neon"},
        save=lambda values: True,
    )
    assert service.load_ui_preferences() == UiPreferences(theme="light")


def test_save_theme_writes_only_supported_value():
    saved = []
    service = SettingsService(load=lambda: {}, save=lambda values: saved.append(values) or True)
    assert service.save_theme("dark") is True
    assert saved == [{"theme": "dark"}]


def test_save_theme_rejects_invalid_value():
    service = SettingsService(load=lambda: {}, save=lambda values: True)
    with pytest.raises(ValueError, match="Unsupported theme"):
        service.save_theme("neon")
```

- [ ] **Step 2: Verify RED**

```bash
python -m pytest tests/test_settings_service.py -v
```

Expected: FAIL because `getpass_app` does not exist.

- [ ] **Step 3: Implement the minimal model and service**

Create `getpass_app/models/preferences.py`:

```python
from dataclasses import dataclass
from typing import Literal

ThemeName = Literal["light", "dark"]


@dataclass(frozen=True)
class UiPreferences:
    theme: ThemeName = "light"
```

Create `getpass_app/services/settings_service.py`:

```python
from __future__ import annotations

from collections.abc import Callable

from getpass_core import config
from getpass_app.models.preferences import UiPreferences


class SettingsService:
    def __init__(
        self,
        load: Callable[[], dict] = config.load_settings,
        save: Callable[[dict], bool] = config.save_settings,
    ) -> None:
        self._load = load
        self._save = save

    def load_ui_preferences(self) -> UiPreferences:
        theme = self._load().get("theme", "light")
        if theme not in ("light", "dark"):
            theme = "light"
        return UiPreferences(theme=theme)

    def save_theme(self, theme: str) -> bool:
        if theme not in ("light", "dark"):
            raise ValueError(f"Unsupported theme: {theme}")
        return self._save({"theme": theme})
```

Create package `__init__.py` files with short module docstrings only.

- [ ] **Step 4: Enforce the no-Qt boundary in tests**

Append to `tests/test_settings_service.py`:

```python
from pathlib import Path


def test_application_layer_has_no_pyside6_imports():
    root = Path(__file__).resolve().parents[1] / "getpass_app"
    for path in root.rglob("*.py"):
        assert "PySide6" not in path.read_text(encoding="utf-8"), path
```

- [ ] **Step 5: Run GREEN**

```bash
python -m pytest tests/test_settings_service.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit the application boundary**

```bash
git add getpass_app tests/test_settings_service.py
git commit -m "feat: add UI-independent application settings service"
```

---

### Task 5: Build the Qt Theme Engine from Existing GET Tokens

**Files:**
- Create: `getpass_qt/__init__.py`
- Create: `getpass_qt/theme/__init__.py`
- Create: `getpass_qt/theme/stylesheet.py`
- Create: `getpass_qt/theme/manager.py`
- Create: `tests/test_qt_theme.py`

**Interfaces:**
- Consumes: `getpass_design.tokens.PALETTES`, `SettingsService`.
- Produces: `build_stylesheet(theme: str) -> str`; `ThemeManager.current_theme`; `ThemeManager.apply(theme: str)`; `ThemeManager.toggle()`; signal `ThemeManager.theme_changed(str)`.

- [ ] **Step 1: Write the QSS and manager tests**

Create `tests/test_qt_theme.py`:

```python
from getpass_app.services.settings_service import SettingsService
from getpass_qt.theme.manager import ThemeManager
from getpass_qt.theme.stylesheet import build_stylesheet


def test_light_stylesheet_uses_get_brand_tokens():
    css = build_stylesheet("light")
    assert "#24305E" in css
    assert "#009CBC" in css or "#007F9A" in css
    assert "#F4F5F9" in css


def test_dark_stylesheet_uses_dark_palette():
    css = build_stylesheet("dark")
    assert "#12172A" in css
    assert "#1A2039" in css


def test_theme_manager_persists_toggle(qapp):
    saved = []
    service = SettingsService(
        load=lambda: {"theme": "light"},
        save=lambda values: saved.append(values) or True,
    )
    manager = ThemeManager(qapp, service)
    manager.apply("light", persist=False)
    assert manager.current_theme == "light"
    manager.toggle()
    assert manager.current_theme == "dark"
    assert saved == [{"theme": "dark"}]
```

- [ ] **Step 2: Verify RED**

```bash
python -m pytest tests/test_qt_theme.py -v
```

Expected: FAIL because `getpass_qt.theme` does not exist.

- [ ] **Step 3: Implement a deterministic QSS builder**

Create `getpass_qt/theme/stylesheet.py` with a single public function:

```python
from getpass_design.tokens import PALETTES


def build_stylesheet(theme: str) -> str:
    if theme not in PALETTES:
        raise ValueError(f"Unknown theme: {theme}")
    p = PALETTES[theme]
    return f"""
QWidget {{
    background: {p.ground};
    color: {p.ink};
    font-family: "Segoe UI";
    font-size: 11pt;
}}
QMainWindow, QWidget#AppShell {{ background: {p.ground}; }}
QFrame#Sidebar {{ background: {p.primary}; }}
QLabel#SidebarBrand {{ color: {p.on_primary}; font-size: 18pt; font-weight: 700; }}
QPushButton[role="nav"] {{
    background: transparent;
    color: {p.on_primary};
    border: 0;
    border-radius: 10px;
    padding: 10px 12px;
    text-align: left;
}}
QPushButton[role="nav"]:checked {{ background: {p.accent_fill}; }}
QPushButton[role="primary"] {{
    background: {p.primary};
    color: {p.on_primary};
    border: 0;
    border-radius: 14px;
    padding: 10px 18px;
    font-weight: 700;
}}
QPushButton[role="accent"] {{
    background: {p.accent_fill};
    color: {p.on_accent};
    border: 0;
    border-radius: 14px;
    padding: 10px 18px;
    font-weight: 700;
}}
QFrame[role="card"] {{
    background: {p.surface};
    border: 1px solid {p.line};
    border-radius: 18px;
}}
QLabel[role="muted"] {{ color: {p.ink_muted}; }}
"""
```

Use only semantic palette values from `getpass_design.tokens`; do not introduce new visual color literals except transparent.

- [ ] **Step 4: Implement theme application/persistence**

Create `getpass_qt/theme/manager.py`:

```python
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from getpass_app.services.settings_service import SettingsService
from getpass_qt.theme.stylesheet import build_stylesheet


class ThemeManager(QObject):
    theme_changed = Signal(str)

    def __init__(self, app: QApplication, settings: SettingsService) -> None:
        super().__init__()
        self._app = app
        self._settings = settings
        self.current_theme = "light"

    def load(self) -> str:
        theme = self._settings.load_ui_preferences().theme
        self.apply(theme, persist=False)
        return theme

    def apply(self, theme: str, *, persist: bool = True) -> None:
        self._app.setStyleSheet(build_stylesheet(theme))
        self.current_theme = theme
        if persist:
            self._settings.save_theme(theme)
        self.theme_changed.emit(theme)

    def toggle(self) -> None:
        self.apply("dark" if self.current_theme == "light" else "light")
```

- [ ] **Step 5: Run theme tests and the renderer guard**

```bash
python -m pytest tests/test_qt_theme.py tests/test_design_tokens.py tests/test_renderer_contract.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit the theme foundation**

```bash
git add getpass_qt/theme getpass_qt/__init__.py tests/test_qt_theme.py
git commit -m "feat: add PySide6 GET theme engine"
```

---

### Task 6: Implement MVVM-lite Navigation and the Variant-A Application Shell

**Files:**
- Create: `getpass_qt/viewmodels/__init__.py`
- Create: `getpass_qt/viewmodels/main_viewmodel.py`
- Create: `getpass_qt/widgets/__init__.py`
- Create: `getpass_qt/widgets/sidebar.py`
- Create: `getpass_qt/views/__init__.py`
- Create: `getpass_qt/views/dashboard.py`
- Create: `getpass_qt/views/migration_page.py`
- Create: `getpass_qt/main_window.py`
- Create: `tests/test_qt_navigation.py`

**Interfaces:**
- Consumes: `ThemeManager`; no core storage/renderer calls.
- Produces: route keys `dashboard`, `vehicle`, `employee`, `journals`, `operations`, `backups`, `diagnostics`, `settings`; `MainViewModel.set_route(route)`; `Sidebar.route_requested(str)`; `MainWindow.active_route`.

- [ ] **Step 1: Write ViewModel route tests**

Create `tests/test_qt_navigation.py` starting with:

```python
import pytest

from getpass_qt.viewmodels.main_viewmodel import MainViewModel


def test_main_viewmodel_defaults_to_dashboard(qtbot):
    vm = MainViewModel()
    assert vm.active_route == "dashboard"


def test_main_viewmodel_emits_valid_route(qtbot):
    vm = MainViewModel()
    with qtbot.waitSignal(vm.route_changed, timeout=1000) as signal:
        vm.set_route("vehicle")
    assert signal.args == ["vehicle"]
    assert vm.active_route == "vehicle"


def test_main_viewmodel_rejects_unknown_route():
    vm = MainViewModel()
    with pytest.raises(ValueError, match="Unknown route"):
        vm.set_route("unknown")
```

- [ ] **Step 2: Verify RED for ViewModel**

```bash
python -m pytest tests/test_qt_navigation.py -v
```

Expected: FAIL because `getpass_qt.viewmodels.main_viewmodel` does not exist.

- [ ] **Step 3: Implement `MainViewModel`**

Create `getpass_qt/viewmodels/main_viewmodel.py`:

```python
from PySide6.QtCore import QObject, Signal

ROUTES = (
    "dashboard",
    "vehicle",
    "employee",
    "journals",
    "operations",
    "backups",
    "diagnostics",
    "settings",
)


class MainViewModel(QObject):
    route_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.active_route = "dashboard"

    def set_route(self, route: str) -> None:
        if route not in ROUTES:
            raise ValueError(f"Unknown route: {route}")
        if route == self.active_route:
            return
        self.active_route = route
        self.route_changed.emit(route)
```

- [ ] **Step 4: Add widget-level shell tests before implementation**

Append to `tests/test_qt_navigation.py`:

```python
from getpass_app.services.settings_service import SettingsService
from getpass_qt.main_window import MainWindow
from getpass_qt.theme.manager import ThemeManager


def _window(qapp):
    service = SettingsService(load=lambda: {"theme": "light"}, save=lambda values: True)
    manager = ThemeManager(qapp, service)
    manager.load()
    window = MainWindow(theme_manager=manager)
    return window


def test_main_window_has_variant_a_sidebar_and_stack(qapp, qtbot):
    window = _window(qapp)
    qtbot.addWidget(window)
    assert window.sidebar.objectName() == "Sidebar"
    assert window.stack.count() == 8
    assert window.active_route == "dashboard"


def test_sidebar_switches_to_vehicle_page(qapp, qtbot):
    window = _window(qapp)
    qtbot.addWidget(window)
    window.sidebar.request_route("vehicle")
    assert window.active_route == "vehicle"


def test_dashboard_primary_action_navigates_to_vehicle(qapp, qtbot):
    window = _window(qapp)
    qtbot.addWidget(window)
    qtbot.mouseClick(window.dashboard.vehicle_button, __import__("PySide6").QtCore.Qt.MouseButton.LeftButton)
    assert window.active_route == "vehicle"
```

- [ ] **Step 5: Verify widget tests RED**

```bash
python -m pytest tests/test_qt_navigation.py -v
```

Expected: ViewModel tests PASS; window/widget tests FAIL because shell files do not exist.

- [ ] **Step 6: Implement the persistent sidebar**

`getpass_qt/widgets/sidebar.py` must expose:

```python
class Sidebar(QFrame):
    route_requested = Signal(str)

    def request_route(self, route: str) -> None:
        self.route_requested.emit(route)

    def set_active(self, route: str) -> None:
        ...
```

Construct checkable text buttons for the eight route keys with Russian labels:

```python
ROUTE_LABELS = {
    "dashboard": "Главная",
    "vehicle": "Пропуск ТС",
    "employee": "Пропуск работника",
    "journals": "Журналы",
    "operations": "Незавершённые",
    "backups": "Резервные копии",
    "diagnostics": "Диагностика",
    "settings": "Настройки",
}
```

Set `self.setObjectName("Sidebar")`, button dynamic property `role="nav"`, and no emoji icons in Phase 1.

- [ ] **Step 7: Implement the dashboard and explicit migration pages**

`getpass_qt/views/dashboard.py` creates three large action buttons:

- `vehicle_button`: `Новый пропуск ТС`;
- `employee_button`: `Пропуск работника`;
- `batch_button`: `Массовая печать`.

Expose signals `vehicle_requested`, `employee_requested`, `batch_requested`.

`getpass_qt/views/migration_page.py` implements:

```python
class MigrationPage(QWidget):
    def __init__(self, title: str, description: str, parent=None):
        ...
```

The description must state that the production workflow remains available in the current Tkinter application during migration; do not present the page as an operational replacement yet.

- [ ] **Step 8: Implement `MainWindow` with fixed shell + `QStackedWidget`**

`getpass_qt/main_window.py` must:

- create a horizontal root layout;
- place `Sidebar` at fixed width 232 px;
- place a right content area with a compact header and `QStackedWidget`;
- create one page per route in `ROUTES`;
- use `DashboardPage` for `dashboard`;
- use `MigrationPage` for the seven workflows not migrated in Phase 1;
- connect sidebar/dashboard signals to `MainViewModel.set_route`;
- connect `route_changed` to stack selection and `Sidebar.set_active`;
- expose read-only `active_route` from the ViewModel;
- include a theme-toggle button connected to `ThemeManager.toggle()`.

No page in Phase 1 may call SQLite, renderer, journal, blacklist or printer APIs.

- [ ] **Step 9: Run navigation/theme/boundary tests**

```bash
python -m pytest tests/test_qt_navigation.py tests/test_qt_theme.py tests/test_settings_service.py -v
```

Expected: PASS.

- [ ] **Step 10: Commit the shell as an independently runnable UI component**

```bash
git add getpass_qt/main_window.py getpass_qt/viewmodels getpass_qt/widgets getpass_qt/views tests/test_qt_navigation.py
git commit -m "feat: add PySide6 variant-A application shell"
```

---

### Task 7: Add the Qt Development Entrypoint and Source Self-Test

**Files:**
- Create: `getpass_qt/app.py`
- Create: `getpass_qt/__main__.py`
- Create: `tests/test_qt_entrypoint.py`
- Verify unchanged: `pass_generator.py`

**Interfaces:**
- Consumes: `SettingsService`, `ThemeManager`, `MainWindow`.
- Produces: `python -m getpass_qt`; `python -m getpass_qt --self-test`; `getpass_qt.app.main(argv: list[str] | None = None) -> int`.

- [ ] **Step 1: Write entrypoint tests**

Create `tests/test_qt_entrypoint.py`:

```python
from pathlib import Path

from getpass_qt.app import main


def test_qt_self_test_returns_zero(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assert main(["--self-test"]) == 0


def test_phase1_keeps_tkinter_as_default_production_entrypoint():
    source = (Path(__file__).resolve().parents[1] / "pass_generator.py").read_text(encoding="utf-8")
    assert "from getpass_ui.app import App" in source
    assert "from getpass_qt" not in source
```

- [ ] **Step 2: Verify RED**

```bash
python -m pytest tests/test_qt_entrypoint.py -v
```

Expected: FAIL because `getpass_qt.app` does not exist.

- [ ] **Step 3: Implement bootstrap with self-test isolation**

`getpass_qt/app.py` must parse only `--self-test` in Phase 1. Before creating `QApplication`, set `QT_QPA_PLATFORM=offscreen` when self-test is requested and the variable is unset.

Use this structure:

```python
from __future__ import annotations

import argparse
import os
import sys

from PySide6.QtWidgets import QApplication

from getpass_app.services.settings_service import SettingsService
from getpass_qt.main_window import MainWindow
from getpass_qt.theme.manager import ThemeManager


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="GET-Passes Qt Preview")
    parser.add_argument("--self-test", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.self_test:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    app = QApplication.instance() or QApplication(["GET-Passes Qt Preview"])
    settings = SettingsService()
    theme = ThemeManager(app, settings)
    theme.load()
    window = MainWindow(theme_manager=theme)

    if args.self_test:
        window.show()
        app.processEvents()
        assert window.active_route == "dashboard"
        assert window.stack.count() == 8
        window.close()
        app.processEvents()
        return 0

    window.show()
    return app.exec()
```

`getpass_qt/__main__.py`:

```python
from getpass_qt.app import main

raise SystemExit(main())
```

- [ ] **Step 4: Keep self-test away from persistent user settings**

Before GREEN, refactor `main()` so self-test injects an in-memory `SettingsService` instead of writing the real `settings.json` when the theme button or startup code runs:

```python
if args.self_test:
    settings = SettingsService(load=lambda: {"theme": "light"}, save=lambda values: True)
else:
    settings = SettingsService()
```

- [ ] **Step 5: Run both source entry points**

```bash
python -m pytest tests/test_qt_entrypoint.py -v
python -m getpass_qt --self-test
python pass_generator.py --self-test
```

Expected: all exit with code 0. The final command proves the existing production smoke path is unchanged.

- [ ] **Step 6: Commit the development entry point**

```bash
git add getpass_qt/app.py getpass_qt/__main__.py tests/test_qt_entrypoint.py
git commit -m "feat: add PySide6 preview entrypoint and self-test"
```

---

### Task 8: Extend CI/Lint/Coverage and Prove Qt Packaging Without Changing Production Releases

**Files:**
- Modify: `pyproject.toml`
- Modify: `.github/workflows/python-app.yml`
- Modify: `.github/workflows/windows-ci.yml`
- Modify: `tests/test_workflows.py`

**Interfaces:**
- Consumes: `python -m getpass_qt --self-test` from Task 7.
- Produces: Linux CI coverage/lint/security for the new packages and a Windows CI-only `GET-Passes-Qt-Preview.exe` smoke artifact; production `GET-Passes.exe` remains the Tkinter application.

- [ ] **Step 1: Add failing workflow-contract assertions**

Extend `tests/test_workflows.py` with:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_python_ci_covers_qt_and_application_packages():
    workflow = (ROOT / ".github" / "workflows" / "python-app.yml").read_text(encoding="utf-8")
    assert "QT_QPA_PLATFORM: offscreen" in workflow
    assert "getpass_app" in workflow
    assert "getpass_design" in workflow
    assert "getpass_qt" in workflow


def test_windows_ci_smokes_qt_source_and_preview_exe():
    workflow = (ROOT / ".github" / "workflows" / "windows-ci.yml").read_text(encoding="utf-8")
    assert "python -m getpass_qt --self-test" in workflow
    assert "GET-Passes-Qt-Preview" in workflow
    assert "getpass_qt\\__main__.py" in workflow or "getpass_qt/__main__.py" in workflow


def test_phase1_production_workflows_still_build_pass_generator():
    for name in ("build-exe.yml", "release.yml"):
        workflow = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
        assert "pass_generator.py" in workflow
        assert "GET-Passes-Qt-Preview" not in workflow
```

- [ ] **Step 2: Verify RED**

```bash
python -m pytest tests/test_workflows.py -v
```

Expected: new assertions fail because CI does not yet know about Qt packages/preview smoke.

- [ ] **Step 3: Expand coverage source list**

Update `pyproject.toml`:

```toml
[tool.coverage.run]
source = ["getpass_core", "getpass_ui", "getpass_app", "getpass_design", "getpass_qt"]
```

Keep the project version `1.1.0`.

- [ ] **Step 4: Update Linux Python CI without removing Tk headless coverage**

In `.github/workflows/python-app.yml` add job-level or step-level environment:

```yaml
env:
  QT_QPA_PLATFORM: offscreen
```

Expand both flake8 commands to:

```text
pass_generator.py getpass_core getpass_ui getpass_app getpass_design getpass_qt tests tools
```

Expand Bandit to:

```bash
python -m bandit -r getpass_core getpass_ui getpass_app getpass_design getpass_qt -ll
```

Keep Xvfb/Tk installation and the existing pytest coverage threshold of 60%.

- [ ] **Step 5: Add Windows Qt source smoke before packaging**

In `.github/workflows/windows-ci.yml`, immediately after `Run tests on Windows`, add:

```yaml
      - name: Smoke-test Qt preview from source
        run: python -m getpass_qt --self-test
```

- [ ] **Step 6: Add a separate CI-only Qt preview executable**

After the existing production unsigned EXE smoke, add:

```yaml
      - name: Build Qt preview EXE
        shell: pwsh
        run: |
          $args = @(
            '--noconfirm',
            '--clean',
            '--onefile',
            '--windowed',
            '--icon', 'app_icon.ico',
            '--name', 'GET-Passes-Qt-Preview'
          )
          if (Test-Path 'app_icon.ico') { $args += @('--add-data', 'app_icon.ico;.') }
          python -m PyInstaller @args 'getpass_qt\__main__.py'

      - name: Smoke-test packaged Qt preview
        shell: pwsh
        run: |
          $check = Start-Process -FilePath 'dist\GET-Passes-Qt-Preview.exe' -ArgumentList '--self-test' -WindowStyle Hidden -PassThru
          if (-not $check.WaitForExit(60000)) {
            $check.Kill()
            throw 'Qt preview smoke test timed out'
          }
          if ($check.ExitCode -ne 0) { throw 'Qt preview smoke test failed' }
```

Do not install the preview EXE through Inno Setup and do not publish/sign it in Phase 1.

- [ ] **Step 7: Run workflow contracts and the complete test suite**

```bash
python -m pytest tests/test_workflows.py -v
python -m pytest --cov --cov-fail-under=60 -v
```

Expected: PASS.

- [ ] **Step 8: Run lint/security locally before commit**

```bash
flake8 pass_generator.py getpass_core getpass_ui getpass_app getpass_design getpass_qt tests tools --count --max-line-length=127 --show-source --statistics
flake8 pass_generator.py getpass_core getpass_ui getpass_app getpass_design getpass_qt tests tools --count --select=C901 --max-complexity=10 --statistics
python -m bandit -r getpass_core getpass_ui getpass_app getpass_design getpass_qt -ll
```

Expected: strict flake8 0; C901 0. For Bandit, preserve the existing reporting convention: Medium 0 / High 0 is the blocking target; do not claim zero total findings if low-severity findings remain.

- [ ] **Step 9: Commit CI/package proof**

```bash
git add pyproject.toml .github/workflows/python-app.yml .github/workflows/windows-ci.yml tests/test_workflows.py
git commit -m "ci: validate PySide6 source and preview packaging"
```

---

### Task 9: Document the Developer Preview and Complete Phase-1 Verification

**Files:**
- Modify: `README.md`
- Verify: `docs/superpowers/specs/2026-09-11-pyside6-v2-ui-design.md`
- Verify: `docs/PYSIDE6_MIGRATION.md`
- Verify: `docs/superpowers/plans/2026-09-11-pyside6-phase1-foundation.md`

**Interfaces:**
- Consumes: completed Phase 1 implementation.
- Produces: explicit developer instructions and evidence that Phase 1 is foundation-only, not production cutover.

- [ ] **Step 1: Add the Qt preview instructions to README**

Add a section equivalent to:

```markdown
## PySide6 preview (GET-Passes 2.0 migration)

The production entry point remains the Tkinter application during Phase 1:

```bash
python pass_generator.py
```

The new PySide6 shell can be launched separately for development:

```bash
python -m getpass_qt
```

Headless smoke test:

```bash
python -m getpass_qt --self-test
```

The preview uses the existing GET brand tokens. Printed passes and badges continue to be produced by the existing renderer; Phase 1 does not replace production issuance workflows.
```

- [ ] **Step 2: Run the protected renderer test before the full suite**

```bash
python -m pytest tests/test_renderer_contract.py tests/test_render.py -v
```

Expected: PASS and no change to `tests/fixtures/renderer_contract.json` after Task 1.

- [ ] **Step 3: Run all source-level verification**

```bash
python -m pytest --cov --cov-fail-under=60 -v
python -m getpass_qt --self-test
python pass_generator.py --self-test
python -m pip_audit -r requirements.txt
```

Expected: PASS; dependency audit reports no known vulnerabilities for the resolved Phase 1 runtime set.

- [ ] **Step 4: Run strict static/security checks**

```bash
flake8 pass_generator.py getpass_core getpass_ui getpass_app getpass_design getpass_qt tests tools --count --max-line-length=127 --show-source --statistics
flake8 pass_generator.py getpass_core getpass_ui getpass_app getpass_design getpass_qt tests tools --count --select=C901 --max-complexity=10 --statistics
python -m bandit -r getpass_core getpass_ui getpass_app getpass_design getpass_qt -ll
```

Expected: flake8 strict 0, C901 0, Bandit Medium 0 / High 0.

- [ ] **Step 5: Verify the production entry point and release pipeline are unchanged**

Run:

```bash
git diff main -- pass_generator.py .github/workflows/build-exe.yml .github/workflows/release.yml installer/GET-Passes.iss
```

Expected: no Phase 1 changes to these production-cutover files, except that the design/plan branch may differ from `main` only in documentation until implementation begins. During the implementation PR, the command must still show no modifications to these four paths.

- [ ] **Step 6: Commit documentation**

```bash
git add README.md
git commit -m "docs: document PySide6 phase 1 preview"
```

- [ ] **Step 7: Push and wait for required CI evidence before marking implementation ready**

Required successful checks:

- Python application — Python 3.13;
- Python application — Python 3.14;
- Security / CodeQL / Gitleaks as configured;
- Windows PR smoke — legacy `GET-Passes.exe` test/install/uninstall;
- Windows PR smoke — Qt source self-test;
- Windows PR smoke — `GET-Passes-Qt-Preview.exe` packaged self-test.

Phase 1 is complete only after all of these are green. No claim of physical printer acceptance or GET-Passes 2.0 production readiness is permitted at this phase.

---

## Phase 1 Exit Criteria

Phase 1 can merge when all statements below are true:

1. `python pass_generator.py` still starts the current Tkinter application.
2. `python pass_generator.py --self-test` still passes.
3. `python -m getpass_qt` launches the new variant-A shell.
4. `python -m getpass_qt --self-test` passes without touching persistent user data.
5. The Qt shell has the persistent sidebar, dashboard, stacked pages and light/dark theme based on existing GET tokens.
6. `getpass_app` contains no PySide6 imports.
7. `getpass_core` contains no PySide6 imports.
8. The renderer-contract manifest is unchanged after its initial baseline commit.
9. Existing renderer tests pass.
10. SQLite schema/migrations are unchanged.
11. Production build/release/installer entry points are unchanged.
12. Linux Python 3.13/3.14 CI is green.
13. Windows legacy packaging/install smoke is green.
14. Windows Qt preview packaging/self-test is green.
15. No physical-printer or stable-2.0 claims are made; those belong to later phases.

## Follow-on Plans After Phase 1

Do not combine these into the Phase 1 implementation PR. Create separate implementation plans after Phase 1 merges:

- Phase 2: vehicle-pass application service + ViewModel + full Qt issuance page + renderer-data parity + A4/A5/PDF/print parity.
- Phase 3: employee-pass service + ViewModel + Qt photo crop workflow + print/PDF parity.
- Phase 4: journals, blacklist, unfinished operations, batch printing, backup/restore and diagnostics using Qt model/view.
- Phase 5: production cutover of `pass_generator.py`, PyInstaller/Inno/release pipeline and physical workstation/printer acceptance.
- Phase 6: remove legacy Tkinter presentation only after rollback is no longer required.
