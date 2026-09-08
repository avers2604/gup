# Внесение вклада

## Установка окружения разработки

```bash
# Клонируем репозиторий
git clone https://github.com/avers2604/gup.git
cd gup

# Создаём виртуальное окружение
python -m venv venv
source venv/bin/activate  # На Windows: venv\Scripts\activate

# Устанавливаем зависимости
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Запуск тестов

```bash
# Все тесты
python -m pytest

# С покрытием кода
python -m pytest --cov=getpass_core --cov=getpass_ui

# Проверка синтаксиса
pyflakes pass_generator.py getpass_core getpass_ui

# На Linux для тестов интерфейса
xvfb-run -a python -m pytest
```

## Запуск приложения

```bash
python pass_generator.py
```

## Структура кода

- **`getpass_core/`** — бизнес-логика без зависимости от GUI
  - `domain.py` — доменные объекты (даты, номера, госномера)
  - `storage.py` — работа с журналами и БД машин
  - `render.py` — отрисовка пропусков и бейджей
  - `pdfwriter.py`, `printing.py` — PDF и печать

- **`getpass_ui/`** — интерфейс на Tkinter
  - `app.py` — главное окно
  - `pass_tab.py`, `badge_tab.py` — формы ввода
  - `journal.py` — просмотр журналов
  - `batch.py` — массовая печать

- **`tests/`** — автоматические тесты

## Перед отправкой PR

1. ✅ Тесты проходят: `pytest`
2. ✅ Нет ошибок синтаксиса: `pyflakes`
3. ✅ Изменения не содержат персональных данных
4. ✅ Коммит-сообщения на понятном вам языке

## Внимание

Репозиторий содержит функциональность для работы с персональными данными (ФИО, телефоны, фото). Любые изменения, связанные с хранением или обработкой таких данных, требуют особой осторожности.
