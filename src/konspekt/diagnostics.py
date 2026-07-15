"""Small local diagnostic log for errors hidden by a windowed executable."""

from __future__ import annotations

import traceback
from datetime import UTC, datetime
from pathlib import Path

from .bbb_import import default_library_path


MAX_LOG_BYTES = 1_000_000


def diagnostic_log_path() -> Path:
    return default_library_path().parent / "logs" / "konspekt.log"


def record_exception(area: str, error: BaseException) -> Path | None:
    """Append a traceback without request bodies, headers, or other app state."""

    path = diagnostic_log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _rotate_if_needed(path)
        timestamp = datetime.now(UTC).isoformat(timespec="seconds")
        trace = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        ).rstrip()
        with path.open("a", encoding="utf-8", newline="\n") as output:
            output.write(f"[{timestamp}] {area}\n{trace}\n\n")
    except OSError:
        return None
    return path


def _rotate_if_needed(path: Path) -> None:
    if not path.is_file() or path.stat().st_size < MAX_LOG_BYTES:
        return
    previous = path.with_suffix(".previous.log")
    previous.unlink(missing_ok=True)
    path.replace(previous)
