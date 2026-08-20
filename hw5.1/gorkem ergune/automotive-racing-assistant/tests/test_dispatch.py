"""chat.run_tool_calls dispatch mantigi: bilinen/bilinmeyen arac, arac istisnasi,
eksik/bozuk argumanlar. Hicbiri unhandled istisna FIRLATMAMALI."""

import unittest
from unittest import mock

import chat
import tools


def _call(name, arguments):
    return {"function": {"name": name, "arguments": arguments}}


class RunToolCallsTests(unittest.TestCase):
    def test_known_tool_executes(self):
        msgs = chat.run_tool_calls([_call("check_part_status", {"component": "aku"})])
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["role"], "tool")
        self.assertEqual(msgs[0]["tool_name"], "check_part_status")
        self.assertIn("Aku", msgs[0]["content"])

    def test_unknown_tool_is_graceful(self):
        msgs = chat.run_tool_calls([_call("nonexistent_tool", {})])
        self.assertEqual(len(msgs), 1)
        self.assertIn("adinda bir arac yok", msgs[0]["content"])

    def test_tool_exception_is_caught(self):
        def boom(**_kwargs):
            raise ValueError("patladi")

        with mock.patch.dict(tools.TOOLS, {"boom": boom}):
            msgs = chat.run_tool_calls([_call("boom", {})])
        self.assertIn("Arac calistirilamadi", msgs[0]["content"])
        self.assertIn("patladi", msgs[0]["content"])

    def test_missing_arguments_none(self):
        # arguments None ise {} gibi ele alinmali; check_part_status varsayilanla calisir.
        msgs = chat.run_tool_calls([{"function": {"name": "check_part_status"}}])
        self.assertIn("belirtmelisiniz", msgs[0]["content"])

    def test_invalid_extra_argument_is_caught(self):
        # Fonksiyonun kabul etmedigi bir kwarg -> TypeError -> yakalanir, cokme yok.
        msgs = chat.run_tool_calls([_call("check_part_status", {"bad_kwarg": 1})])
        self.assertIn("Arac calistirilamadi", msgs[0]["content"])

    def test_malformed_call_missing_function(self):
        # Yapisal olarak bozuk cagri (function/name yok) cokme yapmamali.
        msgs = chat.run_tool_calls([{}, {"function": {}}])
        self.assertEqual(len(msgs), 2)
        for m in msgs:
            self.assertIn("Bicimi bozuk", m["content"])

    def test_multiple_calls_return_multiple_messages(self):
        msgs = chat.run_tool_calls([
            _call("check_part_status", {"component": "aku"}),
            _call("get_race_regulations", {"topic": "guvenlik"}),
        ])
        self.assertEqual(len(msgs), 2)
        self.assertEqual([m["tool_name"] for m in msgs], ["check_part_status", "get_race_regulations"])

    def test_log_tool_call_never_raises(self):
        # Windows cp1254 emoji sorunu: loglama asla cokmemeli.
        try:
            chat._log_tool_call("check_part_status", {"component": "aku"})
        except Exception as exc:  # pragma: no cover
            self.fail(f"_log_tool_call raised: {exc}")


if __name__ == "__main__":
    unittest.main()
