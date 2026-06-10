from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from hunt.local_llm import generate_with_local_llm


class TestLocalLlm(unittest.TestCase):
    def test_generate_uses_model_argument_not_environment(self) -> None:
        response = Mock()
        response.ok = True
        response.json.return_value = {"response": "hello"}

        with patch.dict("os.environ", {"OLLAMA_MODEL": "wrong-model"}, clear=True):
            with patch("hunt.local_llm.requests.post", return_value=response) as post:
                output = generate_with_local_llm(
                    "Prompt",
                    model="configured-model",
                    temperature=0.1,
                )

        self.assertEqual(output, "hello")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "configured-model")

    def test_json_mode_sends_format_json(self) -> None:
        response = Mock()
        response.ok = True
        response.json.return_value = {"response": '{"ok": true}'}

        with patch("hunt.local_llm.requests.post", return_value=response) as post:
            generate_with_local_llm("Prompt", model="configured-model", json_mode=True)

        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["format"], "json")
        self.assertIn("<|im_start|>", payload["options"]["stop"])
        self.assertEqual(payload["options"]["repeat_penalty"], 1.1)

    def test_json_mode_retries_without_format_if_unsupported(self) -> None:
        unsupported = Mock()
        unsupported.ok = False
        unsupported.status_code = 400
        unsupported.json.return_value = {"error": "format json is unsupported"}

        success = Mock()
        success.ok = True
        success.json.return_value = {"response": '{"ok": true}'}

        with patch("hunt.local_llm.requests.post", side_effect=[unsupported, success]) as post:
            output = generate_with_local_llm("Prompt", model="configured-model", json_mode=True)

        self.assertEqual(output, '{"ok": true}')
        first_payload = post.call_args_list[0].kwargs["json"]
        second_payload = post.call_args_list[1].kwargs["json"]
        self.assertEqual(first_payload["format"], "json")
        self.assertNotIn("format", second_payload)


if __name__ == "__main__":
    unittest.main()
