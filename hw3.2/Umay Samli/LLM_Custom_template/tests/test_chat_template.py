import unittest
from pathlib import Path

from jinja2 import Environment, StrictUndefined


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = PROJECT_ROOT / "chat_template.jinja"


def raise_exception(message):
    """Hugging Face'in şablona sunduğu yardımcı fonksiyonu taklit eder."""
    raise ValueError(message)


class ChatTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        environment = Environment(undefined=StrictUndefined)
        cls.template = environment.from_string(
            TEMPLATE_PATH.read_text(encoding="utf-8")
        )

    def render(self, messages, *, add_generation_prompt=False):
        return self.template.render(
            messages=messages,
            bos_token="<s>",
            eos_token="</s>",
            add_generation_prompt=add_generation_prompt,
            raise_exception=raise_exception,
        )

    def test_system_and_user_with_generation_prompt(self):
        messages = [
            {"role": "system", "content": "Her zaman Türkçe cevap ver."},
            {"role": "user", "content": "Türkiye'nin başkenti neresidir?"},
        ]

        actual = self.render(messages, add_generation_prompt=True)

        expected = (
            "<s><|system|>\n"
            "Her zaman Türkçe cevap ver.\n"
            "</s>\n"
            "<|user|>\n"
            "Türkiye'nin başkenti neresidir?\n"
            "</s>\n"
            "<|assistant|>\n"
        )
        self.assertEqual(actual, expected)

    def test_complete_conversation_without_generation_prompt(self):
        messages = [
            {"role": "user", "content": "Merhaba"},
            {"role": "assistant", "content": "Merhaba! Nasıl yardımcı olabilirim?"},
        ]

        actual = self.render(messages)

        expected = (
            "<s><|user|>\n"
            "Merhaba\n"
            "</s>\n"
            "<|assistant|>\n"
            "Merhaba! Nasıl yardımcı olabilirim?\n"
            "</s>\n"
        )
        self.assertEqual(actual, expected)

    def test_content_is_trimmed(self):
        actual = self.render([{"role": "user", "content": "  Merhaba  \n"}])
        self.assertIn("<|user|>\nMerhaba\n</s>", actual)

    def test_rejects_unknown_role(self):
        with self.assertRaisesRegex(ValueError, "Desteklenmeyen rol"):
            self.render([{"role": "tool", "content": "sonuç"}])

    def test_rejects_system_message_after_first_position(self):
        messages = [
            {"role": "user", "content": "Merhaba"},
            {"role": "system", "content": "Yeni talimat"},
        ]
        with self.assertRaisesRegex(ValueError, "yalnızca konuşmanın başında"):
            self.render(messages)

    def test_rejects_consecutive_user_messages(self):
        messages = [
            {"role": "user", "content": "Birinci mesaj"},
            {"role": "user", "content": "İkinci mesaj"},
        ]
        with self.assertRaisesRegex(ValueError, "Arka arkaya iki user"):
            self.render(messages)

    def test_rejects_assistant_without_user(self):
        with self.assertRaisesRegex(ValueError, "önce bir user"):
            self.render([{"role": "assistant", "content": "Merhaba"}])

    def test_rejects_non_string_content(self):
        with self.assertRaisesRegex(ValueError, "metin.*olmalıdır"):
            self.render([{"role": "user", "content": ["Merhaba"]}])


if __name__ == "__main__":
    unittest.main()
