from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from konspekt.bbb_import import BBBRecording, inspect_bbb_recording, load_library, save_to_library


MEETING_ID = "f0a35ad2f6165a2fbce2f5d9e6ca241673f63bf8-1758353019485"
PLAYBACK_URL = (
    "https://bbb-lb.tsi.lv/playback/presentation/2.0/playback.html"
    f"?meetingId={MEETING_ID}"
)


class FakeResponse:
    def __init__(self, status_code: int = 200, text: str = "") -> None:
        self.status_code = status_code
        self.text = text


class FakeSession:
    def __init__(self, metadata: dict[str, str]) -> None:
        self.metadata = metadata

    def head(self, url: str, **_: object) -> FakeResponse:
        return FakeResponse(200 if url.endswith(("webcams.mp4", "deskshare.mp4")) else 404)

    def get(self, url: str, **_: object) -> FakeResponse:
        for name, body in self.metadata.items():
            if url.endswith(name):
                return FakeResponse(text=body)
        return FakeResponse(404)


class BBBImportTests(unittest.TestCase):
    def test_inspects_media_title_and_slide_text(self) -> None:
        session = FakeSession(
            {
                "metadata.xml": '<recording><meeting name="Databases 101" /></recording>',
                "presentation_text.json": json.dumps(
                    {"deck": {"slide-1": "Primary keys", "slide-2": ""}}
                ),
                "slides_new.xml": "<popcorn />",
            }
        )

        recording = inspect_bbb_recording(PLAYBACK_URL, session=session)

        self.assertEqual(recording.title, "Databases 101")
        self.assertTrue(recording.audio_video_url.endswith("video/webcams.mp4"))
        self.assertTrue(recording.screen_video_url.endswith("deskshare/deskshare.mp4"))
        self.assertEqual([slide.identifier for slide in recording.slides], ["slide-1", "slide-2"])
        self.assertTrue(recording.has_slide_text)

    def test_saves_one_recording_per_meeting(self) -> None:
        session = FakeSession(
            {
                "metadata.xml": '<recording><meeting name="Databases 101" /></recording>',
                "presentation_text.json": "{}",
                "slides_new.xml": "<popcorn />",
            }
        )
        recording = inspect_bbb_recording(PLAYBACK_URL, session=session)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "library.json"
            save_to_library(recording, path)
            save_to_library(recording, path)

            loaded = load_library(path)

        self.assertEqual(len(loaded), 1)
        self.assertIsInstance(loaded[0], BBBRecording)


if __name__ == "__main__":
    unittest.main()
