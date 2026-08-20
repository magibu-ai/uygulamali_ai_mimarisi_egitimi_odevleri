"""Arac fonksiyonlarinin birim testleri (check_part_status, get_race_regulations)
ve get_weather / internet_search'in HATA yollari (mock'lanmis HTTP ile).

Canli API cagrisi YOKTUR: tum ag erisimi mock'lanir.
"""

import unittest
from unittest import mock

import requests

import tools
import race_data


class CheckPartStatusTests(unittest.TestCase):
    def test_known_component_returns_fields_and_disclaimer(self):
        out = tools.check_part_status("fren balatalari")
        self.assertIn("Fren balatalari", out)
        self.assertIn("Durum:", out)
        self.assertIn("Son muayene:", out)
        self.assertIn(race_data.DATA_DISCLAIMER, out)

    def test_english_alias_resolves(self):
        out = tools.check_part_status("brake pads")
        self.assertIn("Fren balatalari", out)

    def test_all_five_components_known(self):
        for word in ["fren balatalari", "fren diskleri", "lastikler", "motor yagi", "aku"]:
            out = tools.check_part_status(word)
            self.assertNotIn("bulunmuyor", out, f"{word} bilinmeli")

    def test_unknown_component_is_graceful(self):
        out = tools.check_part_status("turbo")
        self.assertIn("bulunmuyor", out)
        self.assertIn("Bilinen bilesenler", out)

    def test_empty_argument(self):
        self.assertIn("belirtmelisiniz", tools.check_part_status(""))

    def test_missing_argument_uses_default(self):
        # Arguman hic verilmezse (varsayilan bos) istisna FIRLATMAMALI.
        self.assertIn("belirtmelisiniz", tools.check_part_status())

    def test_component_with_warning_shows_warning(self):
        out = tools.check_part_status("lastikler")
        self.assertIn("Uyari:", out)


class GetRaceRegulationsTests(unittest.TestCase):
    def test_known_topic_returns_summary_and_disclaimer(self):
        out = tools.get_race_regulations("guvenlik")
        self.assertIn("Guvenlik", out)
        self.assertIn(race_data.DATA_DISCLAIMER, out)

    def test_all_six_topics_known(self):
        for topic in ["frenler", "lastikler", "guvenlik", "elektrik", "surucu", "teknik muayene"]:
            out = tools.get_race_regulations(topic)
            self.assertNotIn("mevcut degil", out, f"{topic} bilinmeli")

    def test_unknown_topic_is_graceful(self):
        out = tools.get_race_regulations("aerodinamik")
        self.assertIn("mevcut degil", out)
        self.assertIn("Bilinen konular", out)

    def test_empty_and_missing_argument(self):
        self.assertIn("belirtmelisiniz", tools.get_race_regulations(""))
        self.assertIn("belirtmelisiniz", tools.get_race_regulations())


class GetWeatherFailureTests(unittest.TestCase):
    def test_empty_city(self):
        self.assertIn("sehir adi", tools.get_weather(""))

    @mock.patch("tools.requests.get")
    def test_city_not_found(self, mock_get):
        mock_get.return_value = mock.Mock(**{"json.return_value": {"results": []}})
        self.assertIn("bulunamadi", tools.get_weather("Xyzville"))

    @mock.patch("tools.requests.get", side_effect=requests.exceptions.ConnectionError("down"))
    def test_network_failure_is_graceful(self, _mock_get):
        out = tools.get_weather("Istanbul")
        self.assertIn("Hava durumu alinamadi", out)


class InternetSearchFailureTests(unittest.TestCase):
    @mock.patch("tools.requests.get")
    @mock.patch("tools.requests.post", side_effect=requests.exceptions.ConnectionError("ddg down"))
    def test_ddg_down_falls_back_to_wikipedia_empty(self, _mock_post, mock_get):
        # DDG cokerse Wikipedia yedegine duser; Wikipedia bos sonuc dondururse
        # UYDURMADAN "sonuc bulunamadi" der.
        mock_get.return_value = mock.Mock(**{"json.return_value": {"query": {"search": []}}})
        out = tools.internet_search("bir sey")
        self.assertIn("sonuc bulunamadi", out)

    @mock.patch("tools.requests.get", side_effect=requests.exceptions.ConnectionError("wiki down"))
    @mock.patch("tools.requests.post", side_effect=requests.exceptions.ConnectionError("ddg down"))
    def test_both_down_is_graceful(self, _mock_post, _mock_get):
        out = tools.internet_search("bir sey")
        self.assertIn("Arama yapilamadi", out)


if __name__ == "__main__":
    unittest.main()
