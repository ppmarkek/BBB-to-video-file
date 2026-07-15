# Konspekt

![Konspekt icon](assets/konspekt.svg)

Windows-приложение для превращения записей BigBlueButton в аккуратные учебные материалы. Оно локально скачивает необходимые дорожки записи, распознаёт речь и текст на экране, собирает контекст и помогает сохранить готовый `lesson.md`.

## Что работает локально

- импорт публичной BBB-записи по ссылке playback;
- извлечение аудио и кадров экрана через FFmpeg;
- транскрибация Faster-Whisper на компьютере;
- OCR кадров через Tesseract;
- контекст для ChatGPT или DeepSeek и сохранение итогового Markdown;
- отображение этапов обработки с процентами.

Аудио, кадры и транскрипция не отправляются в API. При первой транскрибации Faster-Whisper один раз скачает открытую модель `small`; это не расходует API-токены.

## Быстрый старт для разработки

1. Установи Python 3.10+ и открой PowerShell в папке проекта.
2. Выполни:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -e ".[local-ai]"
   .\.venv\Scripts\pythonw.exe -m konspekt
   ```

3. В приложении добавь ссылку BBB, нажми «Подготовить», затем «Собрать пакет».

`scripts\setup_local_ai.ps1` и `scripts\run_konspekt.bat` делают то же самое. Прямые команды выше пригодятся, если Windows запрещает запуск `.ps1`-сценариев.

Для OCR экрана установи Tesseract:

```powershell
winget install UB-Mannheim.TesseractOCR
```

Подробности: [локальная обработка](docs/local-ai.md).

## Готовая Windows-версия

Собери приложение командой:

```powershell
.\scripts\build_konspekt.ps1
```

Результат: `dist\Konspekt\Konspekt.exe`. Копируй всю папку `dist\Konspekt`, а не только `.exe`: рядом лежат FFmpeg, Tesseract, локальные библиотеки и иконка приложения. Инструкция для получателя: [docs/release.md](docs/release.md).

## Структура проекта

```text
src/konspekt/          исходный код приложения и BBB CLI
tests/                 модульные тесты
assets/                единая SVG, PNG и ICO-иконка Konspekt
scripts/               настройка, запуск, сборка и генерация иконки
packaging/             PyInstaller-спецификации
docs/                  инструкции по локальному ИИ и выпуску
pyproject.toml         зависимости и точки входа пакета
```

Основной запуск — `python -m konspekt` или команда `konspekt` после установки пакета. Корневые `study_app.py` и `bbb_import.py` оставлены только как короткие совместимые обёртки для старых запусков.

## Проверка

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONPATH = "$PWD\src"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Дополнительная CLI-утилита

Старый BBB-загрузчик сохранён отдельно от интерфейса. Он скачивает запись и при необходимости собирает MP4:

```powershell
python -m konspekt.bbb_download "https://host/playback/presentation/2.0/playback.html?meetingId=..."
```

Для него есть отдельная сборка: `scripts\build_bbb_downloader.ps1`.
