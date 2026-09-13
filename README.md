# Система выпуска пропусков — СПб ГУП «Горэлектротранс»

Настольное приложение для оформления пропусков на транспортные средства и
постоянных пропусков работников: заполнение, live preview, PDF/печать, журналы
выдачи SQLite, незавершённые операции, массовая печать, backup/restore,
диагностика, настройки и blacklist.

## GET-Passes 2.0

В ветке production-cutover основной интерфейс — **PySide6**. Стабильный релиз
`v2.0.0` ещё не публикуется: перед merge/tag обязательны физическая приёмка на
целевом рабочем месте/принтере и доверенная Authenticode-подпись. Полный протокол
находится в [`docs/PHYSICAL_ACCEPTANCE_2_0.md`](docs/PHYSICAL_ACCEPTANCE_2_0.md),
внешний gate отслеживается в issue #41.

Основной запуск:

```bash
python pass_generator.py
```

Headless smoke production UI:

```bash
python pass_generator.py --self-test
```

Временный rollback на прежний Tkinter UI сохранён до завершения физической
приёмки:

```bash
python legacy_pass_generator.py
python legacy_pass_generator.py --self-test
```

`GET-Passes.exe` — production PySide6 candidate. `GET-Passes-Legacy.exe` —
временный rollback, который поставляется рядом, но не получает отдельный ярлык.
Оба используют существующие core/storage/data locations; отдельной базы данных
для Qt нет.

## Запуск на Python

```bash
python -m venv .venv
. .venv/bin/activate          # Linux/macOS
# .venv\Scripts\activate     # Windows PowerShell
python -m pip install -r requirements-dev.txt
python pass_generator.py
```

Поддерживается Python 3.13/3.14; Windows packaging использует Python 3.14.7.
PySide6 закреплён в диапазоне 6.11.x. `tkinter` остаётся зависимостью только для
rollback-исполняемого файла и legacy regression tests до Phase 6 cleanup.

## PySide6 workflows

Все девять маршрутов shell являются реальными workflow:

- **Главная** — навигация и быстрые действия;
- **Пропуск ТС** — A4/A5, live preview, PDF, печать, оборот и durable issuance;
- **Пропуск работника** — фото 3:4, CR80/A4, preview, PDF/печать и журнал;
- **Массовая печать** — CSV UTF-8-SIG/CP1251, review, progress/cancel, batch PDF;
- **Журналы** — model/view таблицы, фильтры, история, revoke и XLSX export;
- **Незавершённые** — recovery prepared issuance операций;
- **Резервные копии** — `.gupbak`/ZIP, inspect, integrity check и safe restore;
- **Диагностика** — read-only runtime/paths/SQLite integrity snapshot;
- **Настройки** — operator defaults и model/view управление blacklist.

Длительные batch/backup/diagnostics операции выполняются вне GUI thread через
`QThreadPool`/`QRunnable`.

## Совместимость данных и печати

Phase 5 **не меняет** SQLite schema, миграции, форматы журналов, пути данных,
renderer, бланки, координаты, шрифты или assets. Существующий `gup.sqlite3`,
`settings.json`, blacklist, photos и pending operations используются напрямую.

Бланки ТС и работников строятся существующими `getpass_core/blank.py` и
`getpass_core/render.py`; `template.png` не требуется. Изменение UI не является
изменением печатного макета.

Каталог данных выбирается действующим `getpass_core.config`:

1. writable `data/` рядом с программой;
2. каталог программы, если там уже находятся данные прежней версии;
3. `%LOCALAPPDATA%\GET-Passes`, если запись рядом запрещена.

В каталоге данных находятся `settings.json`, `gup.sqlite3`, фотографии,
`blacklist.json`, backups и `crash.log` согласно действующим core-механизмам.

> Журналы, фото и backup-файлы содержат персональные данные. `.gupbak`
> шифруется пользовательским паролем; обычный ZIP не шифруется и требует
> ограниченного доступа к носителю.

## Сборка Windows

Production EXE:

```powershell
python -m PyInstaller --noconfirm --clean --onefile --windowed `
  --icon app_icon.ico --name GET-Passes pass_generator.py
```

Rollback EXE:

```powershell
python -m PyInstaller --noconfirm --clean --onefile --windowed `
  --icon app_icon.ico --name GET-Passes-Legacy legacy_pass_generator.py
```

CI добавляет `assets/`, `fonts/`/`fronts/` и icon через `--add-data`.
`installer/GET-Passes.iss` версии **2.0.0** устанавливает оба EXE, но Start Menu
и desktop shortcut указывают только на `GET-Passes.exe`.

### GitHub Actions

- `python-app.yml` — Python 3.13/3.14, flake8/C901, full pytest + coverage,
  dependency audit, Bandit;
- `security.yml` — gitleaks и CodeQL;
- `windows-ci.yml` — tests, source smoke обоих launchers, сборка/self-test обоих
  EXE, Inno Setup, install/self-test обоих установленных EXE и uninstall;
- `build-exe.yml` — main candidate build, portable ZIP и installer, с приоритетом
  Artifact Signing → Azure Key Vault → PFX;
- `release.yml` — только tag `v*`, версия tag должна совпасть с `pyproject.toml`,
  а trusted signing обязателен.

Portable ZIP содержит `GET-Passes.exe` и `GET-Passes-Legacy.exe` вместе с
ресурсами. Stable release `v2.0.0` запрещён до выполнения
`docs/PHYSICAL_ACCEPTANCE_2_0.md`.

## Основные возможности

### Пропуск ТС

- два пропуска на A4 или один на A5;
- автоподстановка сохранённых данных автомобиля без восстановления старых ФИО
  водителя/телефона/зоны;
- live preview существующим renderer;
- односторонняя, автоматическая duplex и manual-flip печать;
- PDF и durable `prepare → output → confirm`.

### Пропуск работника

- кадрирование фото с общей core-геометрией;
- предупреждения дубликатов и blacklist;
- `card`, `a4_grid`, `a4_single`;
- PDF/печать и durable issuance.

### Журналы и recovery

- SQLite вместо runtime CSV/XLSX хранения;
- поиск, status/date/context filters, sorting, pagination;
- optimistic edit/history/revoke;
- XLSX snapshot текущей страницы;
- recovery prepared операций после ошибки/прерывания внешнего вывода.

### Batch

- CSV `;`, UTF-8-SIG и CP1251 fallback;
- отдельные vehicle/badge templates;
- validation preview перед output;
- два ТС на A4 и 3×3 badge grid;
- progress/cancel и recoverable confirm failure.

### Backup и диагностика

- encrypted `.gupbak` и обычный ZIP;
- checksum + SQLite integrity validation;
- rollback при неуспешном restore;
- диагностика Python/paths/database size/integrity/recent backups.

## Дизайн и архитектура

- `getpass_core/` — domain/storage/render/printing/backup, без Qt/Tk зависимости;
- `getpass_app/` — UI-независимый application boundary;
- `getpass_design/` — presentation-neutral design tokens;
- `getpass_qt/` — production PySide6 UI candidate, MVVM-lite/model-view;
- `getpass_ui/` — временный Tkinter rollback до завершения Phase 6;
- `pass_generator.py` — production PySide6 launcher;
- `legacy_pass_generator.py` — временный rollback launcher.

PySide6 и Tkinter используют одни и те же core storage/render/printing contracts.

## Тесты

```bash
pip install -r requirements-dev.txt
python -m pytest
xvfb-run -a python -m pytest
python pass_generator.py --self-test
python legacy_pass_generator.py --self-test
```

Windows CI дополнительно проверяет оба собранных EXE и оба EXE после установки
Setup.exe.

## DPI и доступность

Qt production candidate должен пройти физическую проверку Windows scaling
100/125/150/200%. Основные формы поддерживают клавиатурную навигацию,
семантические состояния ошибок и светлую/тёмную тему. CI проверяет headless
поведение, но не заменяет визуальную проверку на целевом мониторе.

## Production cutover gate

Software candidate может считаться готовым только после зелёных Python,
Security и Windows workflows. Фактический production cutover и стабильный
`v2.0.0` дополнительно требуют:

1. trusted Authenticode signing;
2. выполнения `docs/PHYSICAL_ACCEPTANCE_2_0.md` на реальном ПК/принтере;
3. подтверждения rollback `GET-Passes-Legacy.exe`;
4. фиксации решения `ACCEPTED` в issue #41.

До этого PR production-cutover должен оставаться неперелитым в `main`, а tag
`v2.0.0` не создаётся.
