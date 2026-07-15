from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bbb_import import BBBRecording
from local_pipeline import TranscriptSegment, prepare_lecture


class LocalPipelineTests(unittest.TestCase):
    def test_prepares_transcript_frames_and_local_ocr(self) -> None:
        recording = BBBRecording(
            meeting_id="meeting-1",
            source_url="https://example.test/playback?meetingId=meeting-1",
            title="Test lecture",
            imported_at="2026-07-15T10:00:00+00:00",
            audio_video_url="https://example.test/video/webcams.webm",
            screen_video_url="https://example.test/deskshare/deskshare.webm",
            slides=(),
        )

        def downloader(_: str, destination: Path, __: object) -> None:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"media")

        def transcribe(_: Path, __: str | None) -> tuple[TranscriptSegment, ...]:
            return (TranscriptSegment(1.2, 4.8, "Hello local transcription"),)

        def run_ffmpeg(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            output = Path(command[-1])
            if "frame-%04d.jpg" in str(output):
                output.parent.mkdir(parents=True, exist_ok=True)
                (output.parent / "frame-0001.jpg").write_bytes(b"frame")
                (output.parent / "frame-0002.jpg").write_bytes(b"frame")
            else:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(b"audio")
            return subprocess.CompletedProcess(command, 0, "", "")

        with tempfile.TemporaryDirectory() as temporary:
            with patch("local_pipeline.resolve_ffmpeg", return_value="ffmpeg"):
                prepared = prepare_lecture(
                    recording,
                    directory=Path(temporary),
                    downloader=downloader,
                    transcriber=transcribe,
                    ocr_reader=lambda frame: f"Text from {frame.name}",
                    command_runner=run_ffmpeg,
                )

            transcript = prepared.transcript_path.read_text(encoding="utf-8")
            notes = (Path(temporary) / "screen-notes.json").read_text(encoding="utf-8")

        self.assertIn("00:00:01", transcript)
        self.assertIn("Hello local transcription", transcript)
        self.assertIn("frame-0002.jpg", notes)
        self.assertEqual(prepared.frame_count, 2)

    def test_reuses_existing_audio_and_skips_screen_when_absent(self) -> None:
        recording = BBBRecording(
            meeting_id="meeting-2",
            source_url="https://example.test/playback?meetingId=meeting-2",
            title="Audio lecture",
            imported_at="2026-07-15T10:00:00+00:00",
            audio_video_url="https://example.test/video/webcams.webm",
            screen_video_url=None,
            slides=(),
        )

        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            (target / "webcams.webm").write_bytes(b"media")

            def run_ffmpeg(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                Path(command[-1]).write_bytes(b"audio")
                return subprocess.CompletedProcess(command, 0, "", "")

            with patch("local_pipeline.resolve_ffmpeg", return_value="ffmpeg"):
                prepared = prepare_lecture(
                    recording,
                    directory=target,
                    downloader=lambda *_: self.fail("download should not run"),
                    transcriber=lambda *_: (),
                    command_runner=run_ffmpeg,
                )

        self.assertIsNone(prepared.screen_notes_path)
        self.assertEqual(prepared.frame_count, 0)


if __name__ == "__main__":
    unittest.main()
