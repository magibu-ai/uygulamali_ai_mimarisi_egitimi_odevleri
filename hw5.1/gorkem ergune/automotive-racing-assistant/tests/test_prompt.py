"""Sistem prompt'u icin deterministik koruma (regression guard) testleri.

Model CAGIRILMAZ; yalnizca prompt metninin Faz 3 kararlarini korudugunu dogrular.
"""

import datetime
import unittest

import chat
import tools


class SystemPromptGuardTests(unittest.TestCase):
    def test_max_tool_rounds_is_five(self):
        self.assertEqual(chat.MAX_TOOL_ROUNDS, 5)

    def test_mentions_all_four_tools(self):
        for name in ["get_weather", "check_part_status", "get_race_regulations", "internet_search"]:
            self.assertIn(name, chat.SYSTEM_PROMPT)

    def test_states_demo_data_limitation(self):
        self.assertIn("DEMO", chat.SYSTEM_PROMPT)

    def test_current_year_grounding_in_search_schema(self):
        # Faz 3'te modelin eski yil ("2023") uydurmasina karsi eklenen zaman baglami.
        # Sistem prompt'una eklemek no-tool davranisini regresyona ugrattigi icin (olculdu),
        # bunun yerine internet_search'in query aciklamasina konuldu.
        year = str(datetime.date.today().year)
        search = next(s for s in tools.TOOL_SCHEMAS if s["function"]["name"] == "internet_search")
        self.assertIn(year, search["function"]["parameters"]["properties"]["query"]["description"])

    def test_no_call_syntax_examples(self):
        # Faz 3 bulgusu: prompt icinde arac cagirma sozdizimi ornegi (arg=deger)
        # 7B modelde metin sizintisina yol aciyordu. Bu tekrar EKLENMEMELI.
        for leak in ['component="', 'topic="', 'city="', 'query="']:
            self.assertNotIn(leak, chat.SYSTEM_PROMPT, f"prompt call-syntax ornegi icermemeli: {leak}")


if __name__ == "__main__":
    unittest.main()
