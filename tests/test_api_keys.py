"""Key rotation and failure handling without calling the PSU gateway."""
import io
import os
import unittest
import urllib.error
from unittest.mock import patch

from pipelines.llm import api_client, providers
from pipelines.llm.config import GenConfig
from pipelines.llm.ollama_client import LLMResult


class ApiKeysTests(unittest.TestCase):
    def setUp(self):
        api_client._key_blocked_until.clear()
        api_client._next_key = 0
        self.env = patch.dict(os.environ, {"API_KEY_1": "first", "API_KEY_2": "second",
                                           "API_KEY_3": "third"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        api_client._key_blocked_until.clear()

    def test_round_robin(self):
        used = []
        def post(payload, key):
            used.append(key)
            return {"choices": [{"message": {"content": "ok"}}]}
        with patch.object(api_client, "_post", side_effect=post):
            for _ in range(4):
                api_client.chat("PSU-LLM/psu-gemma", [{"role": "user", "content": "hi"}], GenConfig())
        self.assertEqual(used, ["first", "second", "third", "first"])

    def test_rate_limited_key_switches_immediately(self):
        used = []
        def post(payload, key):
            used.append(key)
            if key == "first":
                raise urllib.error.HTTPError("url", 429, "limit", {"Retry-After": "120"}, io.BytesIO(b"limit"))
            return {"choices": [{"message": {"content": "ok"}}]}
        with patch.object(api_client, "_post", side_effect=post):
            result = api_client.chat("PSU-LLM/psu-gemma", [], GenConfig())
        self.assertEqual(result.text, "ok")
        self.assertEqual(used, ["first", "second"])
        self.assertNotIn("first", api_client._candidates())

    def test_bad_key_is_skipped_and_single_key_still_supported(self):
        with patch.object(api_client, "_post", side_effect=lambda payload, key:
                          (_ for _ in ()).throw(urllib.error.HTTPError("url", 401, "bad", {}, io.BytesIO(b"bad")))
                          if key == "first" else {"choices": [{"message": {"content": "ok"}}]}):
            self.assertEqual(api_client.chat("model", [], GenConfig()).text, "ok")
        with patch.dict(os.environ, {"API_KEY_1": "", "API_KEY_2": "", "API_KEY_3": "", "API_KEY": "old"}):
            self.assertEqual(api_client.api_keys(), ["old"])

    def test_all_keys_fail_then_uses_local_fallback(self):
        with patch.object(api_client, "_post", side_effect=urllib.error.HTTPError(
                "url", 429, "limit", {"Retry-After": "60"}, io.BytesIO(b"limit"))):
            with patch.object(providers.ollama_client, "chat", return_value=LLMResult("local answer", "local")):
                result = providers.chat("api:PSU-LLM/psu-gemma", [], GenConfig(), fallback="local")
        self.assertEqual(result.text, "local answer")
        self.assertEqual(result.metrics["provider"], "local(fallback)")


if __name__ == "__main__":
    unittest.main()
