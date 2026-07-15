from __future__ import annotations

import unittest
from unittest.mock import patch

from konspekt.__main__ import main


class ModuleEntrypointTests(unittest.TestCase):
    def test_dispatches_private_chatgpt_auth_window(self) -> None:
        with patch(
            "konspekt.chatgpt_auth_window.main",
            return_value=7,
        ) as auth_main:
            result = main(["--chatgpt-auth-window"])

        self.assertEqual(result, 7)
        auth_main.assert_called_once_with([])


if __name__ == "__main__":
    unittest.main()
