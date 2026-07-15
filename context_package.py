"""Build a compact local context package from prepared lecture materials."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from bbb_import import BBBRecording, SlideInfo
from local_pipeline import ScreenNote, TranscriptSegment, default_lecture_directory


class ContextPackageError(RuntimeError):
    """The prepared lecture files cannot be turned into a chat context yet."""


ProgressCallback = Callable[[str], None]


@dataclass(frozen=True)
class TimelineBlock:
    start_seconds: float
    end_seconds: float
    text: str


@dataclass(frozen=True)
class ContextPackage:
    directory: Path
    markdown_path: Path
    json_path: Path
    prompt_path: Path
    timeline_block_count: int
    slide_count: int
    screen_note_count: int


def context_package_is_ready(recording: BBBRecording) -> bool:
    """Return whether the lecture already has the two files needed for a chat."""

    target = default_lecture_directory(recording)
    return (target / "lesson-context.md").is_file() and (target / "lesson-prompt.md").is_file()


def build_context_package(
    recording: BBBRecording,
    *,
    directory: Path | None = None,
    progress: ProgressCallback | None = None,
    max_block_seconds: int = 150,
    max_block_characters: int = 2600,
) -> ContextPackage:
    """Create compact, attachable context without invoking an LLM or external API."""

    if max_block_seconds <= 0 or max_block_characters <= 0:
        raise ValueError("Context block limits must be positive")

    notify = progress or _do_nothing
    target = directory or default_lecture_directory(recording)
    transcript_path = target / "transcript.json"
    if not transcript_path.is_file():
        raise ContextPackageError(
            "Сначала подготовь материалы лекции: не найден файл транскрипции."
        )

    notify("Собираем транскрипцию по временным блокам…")
    segments = _read_transcript(transcript_path)
    blocks = _group_transcript(
        segments,
        max_block_seconds=max_block_seconds,
        max_block_characters=max_block_characters,
    )

    notify("Объединяем текст слайдов и заметки с экрана…")
    slides = _unique_slides(recording.slides)
    screen_notes = _read_screen_notes(target / "screen-notes.json")

    payload = {
        "schema_version": 1,
        "lecture": {
            "title": recording.title,
            "meeting_id": recording.meeting_id,
            "source_url": recording.source_url,
        },
        "slides": [asdict(slide) for slide in slides],
        "screen_notes": [asdict(note) for note in screen_notes],
        "transcript_blocks": [asdict(block) for block in blocks],
    }

    json_path = target / "lesson-context.json"
    markdown_path = target / "lesson-context.md"
    prompt_path = target / "lesson-prompt.md"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown_path.write_text(
        _render_context_markdown(recording, slides, screen_notes, blocks),
        encoding="utf-8",
    )
    prompt_path.write_text(_render_lesson_prompt(recording.title), encoding="utf-8")
    notify("Пакет контекста готов для прикрепления в чат.")

    return ContextPackage(
        directory=target,
        markdown_path=markdown_path,
        json_path=json_path,
        prompt_path=prompt_path,
        timeline_block_count=len(blocks),
        slide_count=len(slides),
        screen_note_count=len(screen_notes),
    )


def _read_transcript(path: Path) -> tuple[TranscriptSegment, ...]:
    payload = _read_json(path, "транскрипции")
    if not isinstance(payload, list):
        raise ContextPackageError("Файл транскрипции имеет неверный формат.")

    segments: list[TranscriptSegment] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        try:
            start = float(item["start_seconds"])
            end = float(item["end_seconds"])
        except (KeyError, TypeError, ValueError):
            continue
        text = _normalise_text(str(item.get("text", "")))
        if text:
            segments.append(TranscriptSegment(start, max(start, end), text))
    return tuple(sorted(segments, key=lambda segment: segment.start_seconds))


def _read_screen_notes(path: Path) -> tuple[ScreenNote, ...]:
    if not path.is_file():
        return ()
    payload = _read_json(path, "заметок с экрана")
    if not isinstance(payload, list):
        return ()

    notes: list[ScreenNote] = []
    seen_text: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            continue
        text = _normalise_text(str(item.get("text", "")))
        fingerprint = text.casefold()
        if not text or fingerprint in seen_text:
            continue
        try:
            timestamp = float(item["timestamp_seconds"])
        except (KeyError, TypeError, ValueError):
            continue
        seen_text.add(fingerprint)
        notes.append(
            ScreenNote(
                timestamp_seconds=timestamp,
                image_path=str(item.get("image_path", "")),
                text=text,
            )
        )
    return tuple(sorted(notes, key=lambda note: note.timestamp_seconds))


def _read_json(path: Path, title: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContextPackageError(f"Не удалось прочитать файл {title}.") from exc


def _unique_slides(slides: tuple[SlideInfo, ...]) -> tuple[SlideInfo, ...]:
    unique: list[SlideInfo] = []
    seen_text: set[str] = set()
    for index, slide in enumerate(slides, start=1):
        text = _normalise_text(slide.text)
        fingerprint = text.casefold()
        if fingerprint and fingerprint in seen_text:
            continue
        if fingerprint:
            seen_text.add(fingerprint)
        unique.append(
            SlideInfo(
                identifier=slide.identifier or f"slide-{index}",
                text=text,
                image_url=slide.image_url,
            )
        )
    return tuple(unique)


def _group_transcript(
    segments: tuple[TranscriptSegment, ...],
    *,
    max_block_seconds: int,
    max_block_characters: int,
) -> tuple[TimelineBlock, ...]:
    blocks: list[TimelineBlock] = []
    start: float | None = None
    end = 0.0
    parts: list[str] = []

    def flush() -> None:
        nonlocal start, end, parts
        if start is not None and parts:
            blocks.append(TimelineBlock(start, end, " ".join(parts)))
        start = None
        end = 0.0
        parts = []

    for segment in segments:
        next_text = segment.text
        if start is not None:
            is_too_long = segment.end_seconds - start > max_block_seconds
            is_too_wide = len(" ".join(parts)) + len(next_text) + 1 > max_block_characters
            if is_too_long or is_too_wide:
                flush()
        if start is None:
            start = segment.start_seconds
        end = max(end, segment.end_seconds)
        parts.append(next_text)
    flush()
    return tuple(blocks)


def _render_context_markdown(
    recording: BBBRecording,
    slides: tuple[SlideInfo, ...],
    screen_notes: tuple[ScreenNote, ...],
    blocks: tuple[TimelineBlock, ...],
) -> str:
    lines = [
        f"# Контекст лекции: {recording.title}",
        "",
        "> Этот файл собран локально. Он не является готовым конспектом: передай его в выбранный чат вместе с `lesson-prompt.md`.",
        "",
        "## Источник",
        f"- BBB-запись: {recording.source_url}",
        f"- Идентификатор: `{recording.meeting_id}`",
        "",
        "## Текст со слайдов",
        "",
    ]
    if slides:
        for slide in slides:
            label = slide.identifier.replace("_", " ")
            lines.append(f"### {label}")
            lines.append(slide.text or "Текст на слайде не извлечён.")
            lines.append("")
    else:
        lines.extend(["Текст слайдов недоступен.", ""])

    lines.extend(["## Текст на экране", ""])
    if screen_notes:
        for note in screen_notes:
            lines.append(f"- **{_format_timestamp(note.timestamp_seconds)}** — {note.text}")
        lines.append("")
    else:
        lines.extend(["OCR-заметки с экрана недоступны.", ""])

    lines.extend(["## Транскрипция по времени", ""])
    if blocks:
        for block in blocks:
            lines.append(
                f"### {_format_timestamp(block.start_seconds)} — {_format_timestamp(block.end_seconds)}"
            )
            lines.extend([block.text, ""])
    else:
        lines.append("Речь в записи не была распознана.")

    return "\n".join(lines).rstrip() + "\n"


def _render_lesson_prompt(title: str) -> str:
    return f"""# Инструкция для создания lesson.md

Прикрепи в чат файл `lesson-context.md`, затем отправь текст ниже.

```text
На основе приложенного контекста подготовь один самодостаточный Markdown-файл `lesson.md` для студента.

Тема лекции: «{title}».

Требования:
1. Пиши по-русски, но сохраняй важные термины на исходном языке и поясняй их.
2. Используй только факты из контекста. Не придумывай определения, примеры, формулы или выводы. Неразборчивые места кратко помечай как «не удалось подтвердить по записи».
3. Сделай ясную структуру: название, краткое резюме, цели обучения, основные разделы, ключевые понятия, связь со слайдами/демонстрацией, мини-словарь, вопросы для самопроверки и короткий план повторения.
4. Объединяй транскрипцию со слайдами и текстом экрана: слайды задают структуру, а речь добавляет объяснения и примеры.
5. Для ключевых утверждений указывай время из транскрипции в формате `[ЧЧ:ММ:СС]`, когда оно есть.
6. Используй Markdown с понятными заголовками, короткими абзацами, списками и таблицами только там, где они действительно упрощают учёбу.
7. Верни только содержимое готового `lesson.md`, без вступления о своей работе.
```
"""


def _normalise_text(value: str) -> str:
    return " ".join(value.split())


def _format_timestamp(seconds: float) -> str:
    total = max(0, int(seconds))
    minutes, second = divmod(total, 60)
    hours, minute = divmod(minutes, 60)
    return f"{hours:02d}:{minute:02d}:{second:02d}"


def _do_nothing(_: str) -> None:
    pass
