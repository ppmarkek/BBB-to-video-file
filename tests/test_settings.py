from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from konspekt.settings import (
    DEFAULT_CHATGPT_MODEL,
    AppSettings,
    SettingsError,
    load_settings,
    save_settings,
)


class SettingsTests(unittest.TestCase):
    def test_round_trips_api_settings_without_writing_secret_to_json(self) -> None:
        settings = AppSettings(
            api_provider="openai",
            api_model="gpt-5.6-luna",
            api_key="sk-test-secret-must-not-be-in-json",
            chatgpt_model="gpt-5.5",
            whisper_model="tiny",
            frame_interval_seconds=90,
            ocr_enabled=False,
        )

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "settings.json"
            with (
                patch(
                    "konspekt.settings._protect_secret",
                    return_value="protected-test-value",
                ) as protect,
                patch(
                    "konspekt.settings._unprotect_secret",
                    return_value=settings.api_key,
                ) as unprotect,
            ):
                save_settings(settings, path=path)

                raw_json = path.read_text(encoding="utf-8")
                payload = json.loads(raw_json)
                loaded = load_settings(path=path)

        self.assertEqual(payload["api_provider"], "openai")
        self.assertEqual(payload["api_model"], "gpt-5.6-luna")
        self.assertEqual(payload["chatgpt_model"], "gpt-5.5")
        self.assertEqual(payload["api_key_protected"], "protected-test-value")
        self.assertNotIn(settings.api_key, raw_json)
        self.assertNotIn("api_key", payload)
        protect.assert_called_once_with(settings.api_key)
        unprotect.assert_called_once_with("protected-test-value")
        self.assertEqual(loaded, settings)

    def test_old_settings_default_to_primary_chatgpt_model(self) -> None:
        payload = {
            "schema_version": 1,
            "api_provider": "deepseek",
            "api_model": "deepseek-v4-flash",
            "api_key_protected": "",
            "whisper_model": "base",
            "frame_interval_seconds": 60,
            "ocr_enabled": True,
        }

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "settings.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            loaded = load_settings(path=path)

        self.assertEqual(loaded.chatgpt_model, DEFAULT_CHATGPT_MODEL)

    def test_rejects_empty_chatgpt_model_when_saving(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "settings.json"
            with self.assertRaises(SettingsError):
                save_settings(AppSettings(chatgpt_model="   "), path=path)


if __name__ == "__main__":
    unittest.main()
