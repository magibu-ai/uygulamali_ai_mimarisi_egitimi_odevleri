"""chat.run_conversation (sinirli arac dongusu) testleri.

Qwen GEREKMEZ: `chat` fonksiyonu sahte (scripted) bir fonksiyonla degistirilir.
Amac orkestrasyon mantigini test etmek: durma kosulu, arac calistirma,
coklu arac, bilinmeyen arac, arac istisnasi ve MAX_TOOL_ROUNDS siniri.
"""

import unittest
from unittest import mock

import chat
import tools


def tool_call_msg(name, arguments):
    return {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": name, "arguments": arguments}}]}


def answer_msg(text):
    return {"role": "assistant", "content": text}


class ScriptedChat:
    """Onceden belirlenmis model cevaplarini sirayla dondurur; cagri sayisini tutar."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def __call__(self, messages, model=None, tools=None):
        self.calls += 1
        idx = min(self.calls - 1, len(self.responses) - 1)
        return self.responses[idx]


class RunConversationTests(unittest.TestCase):
    def test_normal_answer_stops_loop(self):
        fake = ScriptedChat([answer_msg("dogrudan cevap")])
        messages = [{"role": "user", "content": "selam"}]
        out = chat.run_conversation(messages, chat=fake)
        self.assertEqual(out["content"], "dogrudan cevap")
        self.assertEqual(fake.calls, 1)

    def test_single_tool_call_then_final_answer(self):
        fake = ScriptedChat([
            tool_call_msg("check_part_status", {"component": "aku"}),
            answer_msg("Akunuz iyi durumda."),
        ])
        messages = [{"role": "user", "content": "aku durumu?"}]
        out = chat.run_conversation(messages, chat=fake)
        self.assertEqual(out["content"], "Akunuz iyi durumda.")
        self.assertEqual(fake.calls, 2)
        # Arac sonucu mesajlara eklenmis olmali.
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        self.assertEqual(len(tool_msgs), 1)
        self.assertEqual(tool_msgs[0]["tool_name"], "check_part_status")

    def test_multiple_tool_calls_in_one_round(self):
        multi = {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "check_part_status", "arguments": {"component": "aku"}}},
            {"function": {"name": "get_race_regulations", "arguments": {"topic": "guvenlik"}}},
        ]}
        fake = ScriptedChat([multi, answer_msg("birlestirilmis cevap")])
        messages = [{"role": "user", "content": "iki sey"}]
        out = chat.run_conversation(messages, chat=fake)
        self.assertEqual(out["content"], "birlestirilmis cevap")
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        self.assertEqual(len(tool_msgs), 2)

    def test_unknown_tool_does_not_crash(self):
        fake = ScriptedChat([
            tool_call_msg("no_such_tool", {}),
            answer_msg("devam ediyoruz"),
        ])
        messages = [{"role": "user", "content": "?"}]
        out = chat.run_conversation(messages, chat=fake)
        self.assertEqual(out["content"], "devam ediyoruz")
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        self.assertIn("adinda bir arac yok", tool_msgs[0]["content"])

    def test_tool_exception_does_not_crash(self):
        def boom(**_kwargs):
            raise RuntimeError("arac patladi")

        fake = ScriptedChat([
            tool_call_msg("boom", {}),
            answer_msg("hata ele alindi"),
        ])
        messages = [{"role": "user", "content": "?"}]
        with mock.patch.dict(tools.TOOLS, {"boom": boom}):
            out = chat.run_conversation(messages, chat=fake)
        self.assertEqual(out["content"], "hata ele alindi")
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        self.assertIn("Arac calistirilamadi", tool_msgs[0]["content"])

    def test_repeated_tool_calls_stop_at_max_rounds(self):
        # Model HER seferinde arac cagirirsa dongu MAX_TOOL_ROUNDS'da durmali (sonsuz degil).
        always = ScriptedChat([tool_call_msg("check_part_status", {"component": "aku"})])
        messages = [{"role": "user", "content": "dur durak bilmez"}]
        out = chat.run_conversation(messages, chat=always)
        self.assertEqual(always.calls, chat.MAX_TOOL_ROUNDS)
        self.assertIn("tool_calls", out)  # son mesaj hala bir arac cagrisi

    def test_respects_custom_max_rounds(self):
        always = ScriptedChat([tool_call_msg("check_part_status", {"component": "aku"})])
        messages = [{"role": "user", "content": "x"}]
        chat.run_conversation(messages, chat=always, max_rounds=2)
        self.assertEqual(always.calls, 2)

    def test_runtimeerror_propagates_for_caller_to_handle(self):
        # Ollama erisilemezse chat RuntimeError firlatir; dongu bunu yutmaz,
        # cagirana (main try/except) iletir ki kullaniciya temiz hata gosterilsin.
        def down(*_a, **_k):
            raise RuntimeError("Ollama'ya baglanilamadi")

        with self.assertRaises(RuntimeError):
            chat.run_conversation([{"role": "user", "content": "q"}], chat=down)


if __name__ == "__main__":
    unittest.main()
