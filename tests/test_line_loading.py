"""จุดเด้งระหว่างบอทคิด (LINE loading animation) — app/line_api.py, app/handlers.py

python -m unittest discover -s tests
"""
import unittest
from unittest.mock import patch

from app import line_api


class LoadingTests(unittest.TestCase):
    def test_calls_loading_endpoint(self):
        with patch.object(line_api, "LINE_CHANNEL_ACCESS_TOKEN", "t"), patch.object(line_api, "_post") as post:
            line_api.show_loading("U123")
        post.assert_called_once_with("/chat/loading/start", {"chatId": "U123", "loadingSeconds": 60})

    def test_failure_does_not_block_reply(self):
        with patch.object(line_api, "LINE_CHANNEL_ACCESS_TOKEN", "t"), \
             patch.object(line_api, "_post", side_effect=OSError("network")):
            line_api.show_loading("U123")      # ต้องไม่ raise

    def test_simulation_mode_is_noop(self):
        with patch.object(line_api, "LINE_CHANNEL_ACCESS_TOKEN", ""), patch.object(line_api, "_post") as post:
            line_api.show_loading("U123")
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
