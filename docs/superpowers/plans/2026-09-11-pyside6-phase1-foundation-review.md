# Phase 1 plan self-review corrections

These corrections are normative when executing `2026-09-11-pyside6-phase1-foundation.md`.

1. Renderer contract test must enumerate the current protected file set (`getpass_core/render.py`, `getpass_core/blank.py`, `getpass_core/fonts.py`, and every file currently under `assets/`, `fonts/`, `fronts/`) and compare both the set of paths and SHA-256 values to the manifest. This catches added/removed protected files as well as edits.
2. `tests/test_qt_theme.py` must compare generated QSS with values from `getpass_design.tokens.LIGHT`/`DARK` instead of hard-coding a manually calculated `accent_fill` shade.
3. `tests/test_qt_navigation.py` must import `Qt` with `from PySide6.QtCore import Qt` and use `Qt.MouseButton.LeftButton`; do not use dynamic `__import__` access.
4. No production file listed under “Explicitly do not modify in Phase 1” may be changed while executing the plan.
