"""ollama_client.chat testleri. Calisan Ollama GEREKMEZ: requests katmani mock'lanir.

Ollama istemci mimarisi degistirilmez; yalnizca dogru cagri ve hata yollari test edilir.
"""

import unittest
from unittest import mock

import requests

import ollama_client


def _ok_response(payload):
    resp = mock.Mock()
    resp.status_code = 200
    resp.json.return_value = payload
    return resp


class ChatRequestTests(unittest.TestCase):
    @mock.patch("ollama_client.requests.post")
    def test_calls_chat_endpoint_with_model_and_messages(self, mock_post):
        mock_post.return_value = _ok_response({"message": {"content": "merhaba"}})
        msgs = [{"role": "user", "content": "selam"}]
        out = ollama_client.chat(msgs, model="qwen2.5:7b-instruct")

        self.assertEqual(out, {"content": "merhaba"})
        url = mock_post.call_args.args[0] if mock_post.call_args.args else mock_post.call_args.kwargs.get("url")
        self.assertTrue(url.endswith("/api/chat"), url)
        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "qwen2.5:7b-instruct")
        self.assertEqual(payload["messages"], msgs)
        self.assertFalse(payload["stream"])
        self.assertIn("temperature", payload["options"])

    @mock.patch("ollama_client.requests.post")
    def test_tools_included_only_when_given(self, mock_post):
        mock_post.return_value = _ok_response({"message": {"content": "x"}})
        ollama_client.chat([{"role": "user", "content": "q"}])
        self.assertNotIn("tools", mock_post.call_args.kwargs["json"])

        ollama_client.chat([{"role": "user", "content": "q"}], tools=[{"a": 1}])
        self.assertIn("tools", mock_post.call_args.kwargs["json"])

    @mock.patch("ollama_client.requests.post", side_effect=requests.exceptions.ConnectionError("no server"))
    def test_connection_error_becomes_runtimeerror(self, _mock_post):
        with self.assertRaises(RuntimeError) as ctx:
            ollama_client.chat([{"role": "user", "content": "q"}])
        self.assertIn("baglanilamadi", str(ctx.exception))

    @mock.patch("ollama_client.requests.post")
    def test_non_200_becomes_runtimeerror(self, mock_post):
        resp = mock.Mock()
        resp.status_code = 500
        resp.text = "sunucu hatasi"
        mock_post.return_value = resp
        with self.assertRaises(RuntimeError) as ctx:
            ollama_client.chat([{"role": "user", "content": "q"}])
        self.assertIn("500", str(ctx.exception))

    @mock.patch("ollama_client.requests.post")
    def test_malformed_response_missing_message(self, mock_post):
        mock_post.return_value = _ok_response({"unexpected": True})
        with self.assertRaises(RuntimeError) as ctx:
            ollama_client.chat([{"role": "user", "content": "q"}])
        self.assertIn("beklenmeyen", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
