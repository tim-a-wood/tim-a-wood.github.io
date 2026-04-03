"""Unit tests for Agent OS / workbench dashboard helpers."""

import unittest

from scripts.workbench_local_control import keys_from_env


class KeysFromEnvTests(unittest.TestCase):
    def test_openai_key_set_when_present(self):
        env = {
            "PIXELLAB_API_KEY": "",
            "GEMINI_API_KEY": "x",
            "OPENAI_API_KEY": "sk-test",
            "RESEND_API_KEY": "",
        }
        keys = keys_from_env(env)
        self.assertTrue(keys["openai_key_set"])
        self.assertTrue(keys["gemini_key_set"])
        self.assertFalse(keys["pixellab_key_set"])

    def test_openai_key_set_false_when_blank(self):
        env = {"OPENAI_API_KEY": "   "}
        keys = keys_from_env(env)
        self.assertFalse(keys["openai_key_set"])


if __name__ == "__main__":
    unittest.main()
