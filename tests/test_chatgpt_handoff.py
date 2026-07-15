from __future__ import annotations

import importlib.util
import inspect
import unittest

from konspekt import app


class ChatGPTWebHandoffRemovalTests(unittest.TestCase):
    def test_legacy_chatgpt_web_handoff_module_is_removed(self) -> None:
        self.assertIsNone(importlib.util.find_spec("konspekt.chatgpt_handoff"))

    def test_application_does_not_open_the_chatgpt_website(self) -> None:
        source = inspect.getsource(app)
        self.assertNotIn("chatgpt.com", source)
        self.assertNotIn("open_chatgpt_handoff", source)


if __name__ == "__main__":
    unittest.main()
