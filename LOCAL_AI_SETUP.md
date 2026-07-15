# Local AI setup

This project can prepare a BBB lecture without sending audio, screen frames, or text to a paid API.

## One-time setup

Run this in PowerShell from the project folder:

```powershell
.\setup_local_ai.ps1
```

It creates `.venv`, installs the open `faster-whisper` runtime and the existing FFmpeg helper. The first transcription downloads the open Whisper `small` model to the local model cache; this is a one-time model download, not token billing.

## Optional local OCR

For text visible on the lecture screen, install Tesseract once:

```powershell
winget install UB-Mannheim.TesseractOCR
```

If Tesseract is absent, the application still saves screen frames and transcription. It explains that OCR was skipped instead of silently claiming that screen text was read.

## Local output

Prepared materials are saved under:

```text
%LOCALAPPDATA%\Konspekt\lectures\<meeting-id>\
```

Each folder contains `audio.wav`, `transcript.md`, `transcript.json`, sampled `frames/`, and (when Tesseract is available) `screen-notes.json`.
