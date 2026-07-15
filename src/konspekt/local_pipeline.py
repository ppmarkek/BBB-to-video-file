"""Local, no-token preparation of an imported BBB lecture for later summarisation."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable, Protocol
from urllib.parse import urlparse

import requests

from .bbb_download import resolve_ffmpeg
from .bbb_import import BBBRecording, default_library_path


class LocalProcessingError(RuntimeError):
    """The local lecture pipeline cannot continue until a local dependency is ready."""


ProgressCallback = Callable[[int, str], None]
DownloadProgressCallback = Callable[[str], None]
MediaDownloader = Callable[[str, Path, DownloadProgressCallback | None], None]


@dataclass(frozen=True)
class TranscriptSegment:
    start_seconds: float
    end_seconds: float
    text: str


@dataclass(frozen=True)
class ScreenNote:
    timestamp_seconds: float
    image_path: str
    text: str


@dataclass(frozen=True)
class PreparedLecture:
    directory: Path
    audio_path: Path
    transcript_path: Path
    screen_notes_path: Path | None
    frame_count: int


class LocalTranscriber(Protocol):
    def __call__(
        self,
        audio_path: Path,
        language: str | None,
    ) -> Iterable[TranscriptSegment]: ...


def default_lecture_directory(recording: BBBRecording) -> Path:
    return default_library_path().parent / "lectures" / recording.meeting_id


def lecture_is_prepared(recording: BBBRecording) -> bool:
    return (default_lecture_directory(recording) / "transcript.md").is_file()


def prepare_lecture(
    recording: BBBRecording,
    *,
    directory: Path | None = None,
    model_name: str = "small",
    language: str | None = None,
    frame_interval_seconds: int = 30,
    progress: ProgressCallback | None = None,
    downloader: MediaDownloader | None = None,
    transcriber: LocalTranscriber | None = None,
    ocr_reader: Callable[[Path], str | None] | None = None,
    command_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> PreparedLecture:
    """Download only the required media and build local study material artefacts.

    A Whisper model is loaded locally. It may download its open model weights on
    first use, but no lecture text, frames, or audio are sent to a paid API.
    """

    if frame_interval_seconds <= 0:
        raise ValueError("frame_interval_seconds must be positive")

    target = directory or default_lecture_directory(recording)
    target.mkdir(parents=True, exist_ok=True)
    download = downloader or download_media
    notify = progress or _do_nothing
    ffmpeg = resolve_ffmpeg()
    if not ffmpeg:
        raise LocalProcessingError(
            "FFmpeg не найден. Запусти .\\setup_local_ai.ps1, затем повтори подготовку."
        )

    notify(4, "Проверяем локальные инструменты…")
    notify(10, "Скачиваем дорожку с голосом преподавателя…")
    webcam_path = target / f"webcams{_extension_from_url(recording.audio_video_url)}"
    if not webcam_path.is_file():
        download(
            recording.audio_video_url,
            webcam_path,
            lambda message: notify(22, message),
        )
    notify(24, "Дорожка с голосом готова.")

    audio_path = target / "audio.wav"
    if not audio_path.is_file():
        notify(30, "Извлекаем аудио локально…")
        _extract_audio(ffmpeg, webcam_path, audio_path, command_runner)
    notify(36, "Аудио подготовлено.")

    notify(40, "Распознаём речь локальной моделью Whisper…")
    recognise = transcriber or faster_whisper_transcribe(model_name)
    segments = tuple(recognise(audio_path, language))
    transcript_path = target / "transcript.md"
    notify(62, "Сохраняем транскрипцию…")
    _write_transcript(target, segments)
    notify(66, "Транскрипция готова.")

    screen_notes_path: Path | None = None
    frame_count = 0
    if recording.screen_video_url:
        notify(70, "Скачиваем демонстрацию экрана…")
        screen_path = target / f"deskshare{_extension_from_url(recording.screen_video_url)}"
        if not screen_path.is_file():
            download(
                recording.screen_video_url,
                screen_path,
                lambda message: notify(76, message),
            )

        frames_dir = target / "frames"
        if not any(frames_dir.glob("frame-*.jpg")):
            notify(80, "Выбираем кадры экрана каждые 30 секунд…")
            _extract_frames(
                ffmpeg,
                screen_path,
                frames_dir,
                frame_interval_seconds,
                command_runner,
            )
        frames = sorted(frames_dir.glob("frame-*.jpg"))
        frame_count = len(frames)

        if ocr_reader is None:
            ocr_reader = default_ocr_reader()
        if ocr_reader is not None:
            notify(88, "Распознаём текст на экране локально…")
            notes = _read_frames(frames, frame_interval_seconds, ocr_reader)
            screen_notes_path = target / "screen-notes.json"
            notify(96, "Сохраняем заметки с экрана…")
            screen_notes_path.write_text(
                json.dumps([asdict(note) for note in notes], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        else:
            notify(96, "Кадры сохранены. OCR пропущен: Tesseract пока не установлен.")

    notify(100, "Материалы готовы для следующего шага.")
    return PreparedLecture(
        directory=target,
        audio_path=audio_path,
        transcript_path=transcript_path,
        screen_notes_path=screen_notes_path,
        frame_count=frame_count,
    )


def download_media(
    url: str,
    destination: Path,
    progress: DownloadProgressCallback | None = None,
) -> None:
    """Download one public BBB asset with bounded, local file handling."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise LocalProcessingError("Не удалось скачать один из файлов BBB-записи.") from exc

    with destination.open("wb") as output:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                output.write(chunk)

    if progress:
        progress(f"Файл сохранён: {destination.name}")


def faster_whisper_transcribe(model_name: str) -> LocalTranscriber:
    """Build a CPU-friendly Faster-Whisper transcriber only when it is needed."""

    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise LocalProcessingError(
            "Локальный Whisper не установлен. Запусти .\\setup_local_ai.ps1, затем повтори подготовку."
        ) from exc

    model = WhisperModel(model_name, device="cpu", compute_type="int8")

    def transcribe(audio_path: Path, language: str | None) -> Iterable[TranscriptSegment]:
        try:
            segments, _ = model.transcribe(
                str(audio_path),
                language=language,
                vad_filter=True,
            )
            return tuple(
                TranscriptSegment(
                    start_seconds=float(segment.start),
                    end_seconds=float(segment.end),
                    text=segment.text.strip(),
                )
                for segment in segments
                if segment.text.strip()
            )
        except Exception as exc:
            raise LocalProcessingError(
                "Whisper не смог обработать аудио. Проверь установку модели и свободное место на диске."
            ) from exc

    return transcribe


def default_ocr_reader() -> Callable[[Path], str | None] | None:
    executable = _find_tesseract_executable()
    if not executable:
        return None

    def read(image_path: Path) -> str | None:
        preferred = [executable, str(image_path), "stdout", "-l", "eng+rus"]
        result = subprocess.run(
            preferred,
            capture_output=True,
            text=True,
            check=False,
            env=_tesseract_environment(executable),
        )
        if result.returncode != 0:
            result = subprocess.run(
                [executable, str(image_path), "stdout"],
                capture_output=True,
                text=True,
                check=False,
                env=_tesseract_environment(executable),
            )
        return result.stdout.strip() or None

    return read


def _find_tesseract_executable() -> str | None:
    candidates = [shutil.which("tesseract")]
    if os.name == "nt":
        candidates.append(
            str(
                Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
                / "Tesseract-OCR"
                / "tesseract.exe"
            )
        )
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    candidates.append(str(bundle_root / "tesseract" / "tesseract.exe"))

    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def _tesseract_environment(executable: str) -> dict[str, str]:
    environment = os.environ.copy()
    tessdata = Path(executable).parent / "tessdata"
    if tessdata.is_dir():
        environment.setdefault("TESSDATA_PREFIX", str(tessdata))
    return environment


def _extract_audio(
    ffmpeg: str,
    source: Path,
    destination: Path,
    command_runner: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    _run_ffmpeg(
        [
            ffmpeg,
            "-y",
            "-nostdin",
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(destination),
        ],
        command_runner,
    )


def _extract_frames(
    ffmpeg: str,
    source: Path,
    frames_dir: Path,
    interval_seconds: int,
    command_runner: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    frames_dir.mkdir(parents=True, exist_ok=True)
    _run_ffmpeg(
        [
            ffmpeg,
            "-y",
            "-nostdin",
            "-i",
            str(source),
            "-vf",
            f"fps=1/{interval_seconds}",
            "-q:v",
            "3",
            str(frames_dir / "frame-%04d.jpg"),
        ],
        command_runner,
    )


def _run_ffmpeg(
    command: list[str],
    command_runner: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    result = command_runner(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise LocalProcessingError(
            "FFmpeg не смог подготовить файл. Проверь доступность записи и свободное место на диске."
        )


def _write_transcript(directory: Path, segments: tuple[TranscriptSegment, ...]) -> None:
    payload = [asdict(segment) for segment in segments]
    (directory / "transcript.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown = ["# Транскрипция", ""]
    for segment in segments:
        markdown.append(f"- **{_format_timestamp(segment.start_seconds)}** — {segment.text}")
    (directory / "transcript.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")


def _read_frames(
    frames: list[Path],
    interval_seconds: int,
    reader: Callable[[Path], str | None],
) -> tuple[ScreenNote, ...]:
    notes: list[ScreenNote] = []
    for index, frame in enumerate(frames):
        text = reader(frame)
        if text:
            notes.append(
                ScreenNote(
                    timestamp_seconds=index * interval_seconds,
                    image_path=str(frame),
                    text=text,
                )
            )
    return tuple(notes)


def _extension_from_url(url: str) -> str:
    extension = Path(urlparse(url).path).suffix
    return extension if extension else ".webm"


def _format_timestamp(seconds: float) -> str:
    total = max(0, int(seconds))
    minutes, second = divmod(total, 60)
    hours, minute = divmod(minutes, 60)
    return f"{hours:02d}:{minute:02d}:{second:02d}"


def _do_nothing(_: int, __: str) -> None:
    pass
