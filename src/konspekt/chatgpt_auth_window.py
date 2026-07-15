"""Private pywebview process used only for the official ChatGPT login URL."""

from __future__ import annotations

import os
from typing import Any, Sequence
from urllib.parse import urlsplit


AUTH_URL_ENV = "KONSPEKT_CHATGPT_AUTH_URL"
_ALLOWED_AUTH_HOSTS = {"auth.openai.com", "chatgpt.com"}


class ChatGPTAuthWindowError(RuntimeError):
    """The internal authentication window could not be opened safely."""


def run_auth_window(auth_url: str | None = None, *, webview_module: Any = None) -> None:
    """Display the OAuth page without exposing browser state to Konspekt."""

    candidate = auth_url
    if candidate is None:
        candidate = os.environ.pop(AUTH_URL_ENV, "")
    validated_url = _validated_auth_url(candidate)

    if webview_module is None:
        try:
            import webview as webview_module
        except ImportError as exc:
            raise ChatGPTAuthWindowError(
                "The embedded authentication window is unavailable."
            ) from exc

    try:
        webview_module.create_window(
            "Вход в ChatGPT",
            validated_url,
            width=760,
            height=860,
            min_size=(560, 640),
        )
        webview_module.start(
            gui="edgechromium",
            debug=False,
            private_mode=True,
        )
    except Exception as exc:
        raise ChatGPTAuthWindowError(
            "The embedded authentication window could not be opened."
        ) from exc


def main(argv: Sequence[str] | None = None) -> int:
    if argv:
        return 2
    try:
        run_auth_window()
    except ChatGPTAuthWindowError:
        return 1
    return 0


def _validated_auth_url(value: str | None) -> str:
    candidate = str(value or "").strip()
    try:
        parsed = urlsplit(candidate)
        port = parsed.port
    except ValueError as exc:
        raise ChatGPTAuthWindowError("Invalid authentication URL.") from exc
    hostname = parsed.hostname.casefold() if parsed.hostname else None
    if (
        parsed.scheme.casefold() != "https"
        or hostname not in _ALLOWED_AUTH_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
    ):
        raise ChatGPTAuthWindowError("Untrusted authentication URL.")
    return candidate
