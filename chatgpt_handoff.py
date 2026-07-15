"""Prepare a user-controlled handoff from local lecture materials to ChatGPT."""

from __future__ import annotations

import os
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from bbb_import import BBBRecording
from local_pipeline import default_lecture_directory


CHATGPT_URL = "https://chatgpt.com/"


class ChatGPTHandoffError(RuntimeError):
    """The local package is not ready for a ChatGPT handoff."""


@dataclass(frozen=True)
class ChatGPTHandoff:
    directory: Path
    context_path: Path
    prompt_path: Path
    instructions_path: Path


def prepare_chatgpt_handoff(
    recording: BBBRecording,
    *,
    directory: Path | None = None,
) -> ChatGPTHandoff:
    """Create a local checklist for a ChatGPT web handoff without an API call."""

    target = directory or default_lecture_directory(recording)
    context_path = target / "lesson-context.md"
    prompt_path = target / "lesson-prompt.md"
    missing = [path.name for path in (context_path, prompt_path) if not path.is_file()]
    if missing:
        raise ChatGPTHandoffError(
            "Сначала собери пакет контекста: не найдены " + ", ".join(missing) + "."
        )

    instructions_path = target / "chatgpt-handoff.md"
    instructions_path.write_text(
        _render_handoff_instructions(recording.title),
        encoding="utf-8",
    )
    return ChatGPTHandoff(
        directory=target,
        context_path=context_path,
        prompt_path=prompt_path,
        instructions_path=instructions_path,
    )


def read_handoff_prompt(handoff: ChatGPTHandoff) -> str:
    """Return the prepared prompt text that the desktop UI can copy locally."""

    try:
        return handoff.prompt_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ChatGPTHandoffError("Не удалось прочитать инструкцию для ChatGPT.") from exc


def launch_chatgpt_handoff(
    handoff: ChatGPTHandoff,
    *,
    open_url: Callable[[str], bool] = webbrowser.open_new_tab,
    open_directory: Callable[[Path], None] | None = None,
) -> None:
    """Open ChatGPT and the local context folder; the user chooses the chat and sends."""

    if not handoff.context_path.is_file() or not handoff.prompt_path.is_file():
        raise ChatGPTHandoffError("Пакет контекста больше недоступен в локальной папке.")

    try:
        opened = open_url(CHATGPT_URL)
        if not opened:
            raise RuntimeError("browser did not accept the address")
        (open_directory or _open_in_file_manager)(handoff.directory)
    except OSError as exc:
        raise ChatGPTHandoffError("Не удалось открыть ChatGPT или папку с материалами.") from exc
    except RuntimeError as exc:
        raise ChatGPTHandoffError("Не удалось открыть ChatGPT в браузере по умолчанию.") from exc


def _open_in_file_manager(directory: Path) -> None:
    if os.name == "nt":
        os.startfile(str(directory))
        return
    webbrowser.open_new_tab(directory.resolve().as_uri())


def _render_handoff_instructions(title: str) -> str:
    return f"""# Передача лекции в ChatGPT

Лекция: **{title}**

Этот этап не использует API. Приложение открывает chatgpt.com, папку с материалами и копирует инструкцию в буфер обмена. Самостоятельно выбрать чат, прикрепить файл и отправить сообщение должен пользователь.

1. В ChatGPT выбери новый или подходящий существующий чат.
2. Прикрепи файл lesson-context.md из этой папки.
3. Вставь подготовленную инструкцию сочетанием Ctrl+V.
4. Проверь, что прикреплён именно файл контекста этой лекции, и отправь сообщение.
5. Сохрани ответ ChatGPT как lesson.md в этой же папке.

В lesson-prompt.md уже заложены требования к структуре, таймкодам и отметке неуверенных фрагментов.
"""
