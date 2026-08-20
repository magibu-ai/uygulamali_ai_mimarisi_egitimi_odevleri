"""SkyBrief tool-calling agent with visible multi-turn traces."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

from tools import TOOL_DEFINITIONS, dispatch_tool

SYSTEM_PROMPT = """Sen SkyBrief adlı, hava durumunu bir arkadaş gibi anlatan bir asistansın.
Kullanıcı sorularını yanıtlamak için SADECE verilen araçları kullanırsın.
Kurallar:
1) Önce resolve_location ile konumu çöz.
2) Anlık hava için get_atmosphere_snapshot çağır.
3) Tahmin istenirse get_horizon_forecast kullan.
4) Hava kalitesi / nefes / AQI sorulursa get_air_quality_index çağır.
5) Dışarı çıkma, koşu, piknik, uygunluk sorulursa önce veri topla; sonra rank_outdoor_viability çağır.
6) Yeterli veri olmadan nihai yanıt verme.
7) Nihai yanıtını sıcak, doğal ve akıcı bir Türkçeyle yaz — sanki bir arkadaşına hava durumunu
   anlatıyormuşsun gibi. Rapor ya da madde listesi gibi konuşma; "AQI:", "PM2.5=" gibi teknik
   etiketler kullanma, sayıları cümlenin içine doğal şekilde yedir (ör. "23 derece, hafif
   rüzgarlı" gibi). Gereksiz tekrar yapma, kısa ve samimi ol.
Birden fazla şehir varsa her biri için ayrı resolve_location + ilgili araçları çağır."""


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]
    result: dict[str, Any]


@dataclass
class AgentTurn:
    index: int
    calls: list[ToolCall] = field(default_factory=list)


@dataclass
class AgentResponse:
    final_answer: str
    turns: list[AgentTurn]
    mode: str

    def format_trace(self) -> str:
        lines: list[str] = []
        for turn in self.turns:
            lines.append(f"[Turn {turn.index}] Araç Çağrıları:")
            for call in turn.calls:
                args = json.dumps(call.arguments, ensure_ascii=False)
                result = json.dumps(call.result, ensure_ascii=False)
                lines.append(f"   -> {call.name}({_args_pretty(call.arguments)})")
                lines.append(f"   <- {result}")
            lines.append("")
        lines.append(f"[Turn {len(self.turns) + 1}] Nihai Yanıt:")
        lines.append(self.final_answer)
        return "\n".join(lines).strip()


def _args_pretty(arguments: dict[str, Any]) -> str:
    parts = []
    for key, value in arguments.items():
        if isinstance(value, str):
            parts.append(f"{key}='{value}'")
        else:
            parts.append(f"{key}={value}")
    return ", ".join(parts)


_KNOWN_PLACES = [
    "New York",
    "Kapadokya",
    "Cappadocia",
    "Nevşehir",
    "Nevsehir",
    "Ürgüp",
    "İstanbul",
    "Istanbul",
    "Ankara",
    "İzmir",
    "Izmir",
    "Bursa",
    "Antalya",
    "Trabzon",
    "Eskişehir",
    "Gaziantep",
    "Konya",
    "Adana",
    "Muğla",
    "Bodrum",
    "Londra",
    "London",
    "Paris",
    "Berlin",
    "Tokyo",
    "Roma",
    "Madrid",
    "Atina",
    "Athens",
    "Dubai",
    "Amsterdam",
    "Viyana",
    "Vienna",
    "Prag",
    "Prague",
    "Barselona",
    "Barcelona",
    "Lisbon",
    "Lizbon",
    "Seoul",
    "Sydney",
    "Cairo",
    "Kahire",
]

_STOPWORDS = {
    "bugün",
    "bugun",
    "yarın",
    "yarin",
    "hava",
    "durumu",
    "kalite",
    "kalitesi",
    "tahmin",
    "tahmini",
    "nasıl",
    "nasil",
    "neler",
    "bana",
    "lütfen",
    "lutfen",
    "what",
    "how",
    "today",
    "tomorrow",
    "weather",
    "should",
    "would",
    "can",
    "the",
    "and",
    "with",
    "from",
    "for",
    "ile",
    "için",
    "icin",
    "veya",
    "yani",
    "gibi",
    "çok",
    "cok",
    "daha",
    "mi",
    "mü",
    "mu",
    "mı",
    "aqi",
    "uv",
    "pm",
    "koşu",
    "kosu",
    "koşuya",
    "kosuya",
    "piknik",
    "fotoğraf",
    "fotograf",
    "aktivite",
    "uygun",
    "uygunluk",
    "sıcak",
    "sicak",
    "soğuk",
    "soguk",
    "yağmur",
    "yagmur",
    "dışarı",
    "disari",
    "çıkılır",
    "cikilir",
    "çıkmak",
    "cikmak",
    "önemli",
    "onemli",
    "önümüzdeki",
    "onumuzdeki",
    "günlük",
    "gunluk",
    "kısa",
    "kisa",
    "brifing",
    "brifingi",
    "plan",
    "planı",
    "plani",
    "ver",
    "nedir",
    "ne",
    "durum",
    "durumda",
    "durumu",
    "skybrief",
    "ufuk",
    "açık",
    "acik",
    "hava",
    "rüzgar",
    "ruzgar",
}

# Geocoding aliases for names Open-Meteo may not resolve directly
_PLACE_ALIASES = {
    "kapadokya": "Nevşehir",
    "cappadocia": "Nevşehir",
    "göreme": "Ürgüp",
    "goreme": "Ürgüp",
    "londra": "London",
    "atina": "Athens",
    "viyana": "Vienna",
    "kahire": "Cairo",
    "lizbon": "Lisbon",
    "barselona": "Barcelona",
}


def _normalize_place(place: str) -> str:
    return _PLACE_ALIASES.get(place.casefold(), place)


_TR_VOICELESS = set("çfhkpsşt")
_TR_FRONT_VOWELS = set("eiöü")
_TR_BACK_VOWELS = set("aıou")


def _turkish_fold(text: str) -> str:
    """Lowercase respecting Turkish dotted/dotless I, for vowel-harmony lookup."""
    return text.replace("İ", "i").replace("I", "ı").lower()


def _locative_suffix(place: str) -> str:
    """Pick the grammatically correct 'da/'de/'ta/'te suffix via Turkish vowel/consonant harmony."""
    folded = _turkish_fold(place)
    last_vowel = next((ch for ch in reversed(folded) if ch in _TR_FRONT_VOWELS | _TR_BACK_VOWELS), None)
    front = last_vowel in _TR_FRONT_VOWELS if last_vowel else False
    last_letter = folded[-1] if folded else ""
    voiceless = last_letter in _TR_VOICELESS
    if voiceless:
        return "'te" if front else "'ta"
    return "'de" if front else "'da"


def _extract_places(query: str) -> list[str]:
    """Lightweight place extraction for the offline planner (TR + EN)."""
    text = query.strip()
    lower_q = text.casefold()
    found: list[str] = []

    # 1) Prefer explicit known places (multi-word first via list order)
    for city in sorted(_KNOWN_PLACES, key=len, reverse=True):
        if city.casefold() in lower_q:
            if city.casefold() not in {x.casefold() for x in found}:
                found.append(city)

    # 2) Apostrophe locatives / possessives: İstanbul'da, Berlin'in
    locative = re.findall(
        r"\b([A-ZÇĞİÖŞÜ][\wçğıöşüÇĞİÖŞÜ]{2,})'(?:da|de|ta|te|dan|den|tan|ten|ın|in|un|ün)\b",
        text,
        flags=re.IGNORECASE,
    )
    for candidate in locative:
        cleaned = candidate.strip(" ,.?!")
        if cleaned.casefold() in _STOPWORDS:
            continue
        if cleaned.casefold() in {x.casefold() for x in found}:
            continue
        found.append(cleaned)

    # 3) "X ile Y" comparison pattern
    comparison = re.findall(
        r"\b([A-ZÇĞİÖŞÜ][\wçğıöşüÇĞİÖŞÜ]{2,})\s+ile\s+([A-ZÇĞİÖŞÜ][\wçğıöşüÇĞİÖŞÜ]{2,})\b",
        text,
        flags=re.IGNORECASE,
    )
    for left, right in comparison:
        for candidate in (left, right):
            if candidate.casefold() in _STOPWORDS:
                continue
            if candidate.casefold() in {x.casefold() for x in found}:
                continue
            found.append(candidate)

    found = _drop_subsumed_places(found)
    normalized = [_normalize_place(item) for item in found[:3]]
    deduped: list[str] = []
    for item in normalized:
        if item.casefold() not in {x.casefold() for x in deduped}:
            deduped.append(item)
    return deduped


def _drop_subsumed_places(items: list[str]) -> list[str]:
    """Drop entries that are just a word-fragment of another multi-word match.

    e.g. "New York'ta" can independently match both "New York" (known place)
    and "York" (locative regex); keep only "New York".
    """
    lowered = [f" {item.casefold()} " for item in items]
    result = []
    for i, item in enumerate(items):
        subsumed = any(
            i != j and lowered[i] != lowered[j] and lowered[i] in lowered[j]
            for j in range(len(items))
        )
        if not subsumed:
            result.append(item)
    return result


def _detect_activity(query: str) -> str:
    q = query.lower()
    if any(k in q for k in ("koşu", "kosu", "running", "jog")):
        return "koşu"
    if any(k in q for k in ("piknik", "picnic")):
        return "piknik"
    if any(k in q for k in ("fotoğraf", "fotograf", "photo")):
        return "fotoğraf"
    return "genel"


def _wants_forecast(query: str) -> bool:
    q = query.lower()
    return any(
        k in q
        for k in (
            "yarın",
            "yarin",
            "tahmin",
            "forecast",
            "hafta",
            "günlük",
            "gunluk",
            "önümüzdeki",
            "onumuzdeki",
            "weekend",
            "tomorrow",
        )
    )


def _wants_air(query: str) -> bool:
    q = query.lower()
    return any(
        k in q
        for k in (
            "hava kalite",
            "air quality",
            "aqi",
            "pm2",
            "pm10",
            "kirlilik",
            "nefes",
            "polen",
        )
    )


def _wants_outdoor(query: str) -> bool:
    q = query.lower()
    return any(
        k in q
        for k in (
            "dışarı",
            "disari",
            "çıkılır",
            "cikilir",
            "uygun",
            "outdoor",
            "koşu",
            "kosu",
            "piknik",
            "yürüyüş",
            "yuruyus",
            "aktivite",
            "gezilir",
            "should i",
        )
    )


def _forecast_days(query: str) -> int:
    q = query.lower()
    if "hafta" in q or "7" in q:
        return 7
    if "5" in q:
        return 5
    if any(k in q for k in ("yarın", "yarin", "tomorrow")):
        return 2
    return 3


def run_offline_agent(user_query: str) -> AgentResponse:
    places = _extract_places(user_query)
    if not places:
        places = ["İstanbul"]

    activity = _detect_activity(user_query)
    need_forecast = _wants_forecast(user_query)
    need_air = _wants_air(user_query) or _wants_outdoor(user_query)
    need_outdoor = _wants_outdoor(user_query)
    days = _forecast_days(user_query)

    # If the query is generic weather, still pull snapshot (+ light forecast)
    if not (need_forecast or need_air or need_outdoor):
        need_forecast = True

    turn1 = AgentTurn(index=1)
    contexts: list[dict[str, Any]] = []

    for place in places:
        loc = dispatch_tool("resolve_location", {"place_name": place})
        turn1.calls.append(ToolCall("resolve_location", {"place_name": place}, loc))
        if "error" in loc:
            contexts.append({"place": place, "error": loc["error"]})
            continue

        lat, lon = loc["latitude"], loc["longitude"]
        snap = dispatch_tool(
            "get_atmosphere_snapshot",
            {"latitude": lat, "longitude": lon},
        )
        turn1.calls.append(
            ToolCall(
                "get_atmosphere_snapshot",
                {"latitude": lat, "longitude": lon},
                snap,
            )
        )

        air = None
        if need_air:
            air = dispatch_tool(
                "get_air_quality_index",
                {"latitude": lat, "longitude": lon},
            )
            turn1.calls.append(
                ToolCall(
                    "get_air_quality_index",
                    {"latitude": lat, "longitude": lon},
                    air,
                )
            )

        forecast = None
        if need_forecast:
            forecast = dispatch_tool(
                "get_horizon_forecast",
                {"latitude": lat, "longitude": lon, "days": days},
            )
            turn1.calls.append(
                ToolCall(
                    "get_horizon_forecast",
                    {"latitude": lat, "longitude": lon, "days": days},
                    forecast,
                )
            )

        contexts.append(
            {
                "place": place,
                "location": loc,
                "snapshot": snap,
                "air": air,
                "forecast": forecast,
            }
        )

    turns = [turn1]
    if need_outdoor:
        turn2 = AgentTurn(index=2)
        for ctx in contexts:
            snap = ctx.get("snapshot") or {}
            air = ctx.get("air") or {}
            forecast = ctx.get("forecast") or {}
            if "error" in ctx or not snap or snap.get("error"):
                continue

            temperature = snap.get("temperature_c")
            wind = snap.get("wind_kmh")
            precip = snap.get("precipitation_mm") or 0
            uv = snap.get("uv_index") or 0

            # Prefer next-day forecast metrics when the question is about tomorrow
            days_data = (forecast.get("days") or []) if isinstance(forecast, dict) else []
            if need_forecast and len(days_data) >= 2:
                nxt = days_data[1]
                temperature = nxt.get("temp_max_c", temperature)
                wind = nxt.get("wind_max_kmh", wind)
                precip = nxt.get("precip_mm", precip) or 0
                uv = nxt.get("uv_index_max", uv) or 0
            elif need_forecast and days_data:
                today = days_data[0]
                temperature = today.get("temp_max_c", temperature)
                wind = today.get("wind_max_kmh", wind)
                precip = today.get("precip_mm", precip) or 0
                uv = today.get("uv_index_max", uv) or 0

            args = {
                "temperature_c": temperature,
                "wind_kmh": wind,
                "precipitation_mm": precip,
                "uv_index": uv,
                "european_aqi": air.get("european_aqi"),
                "activity": activity,
            }
            ranked = dispatch_tool("rank_outdoor_viability", args)
            turn2.calls.append(ToolCall("rank_outdoor_viability", args, ranked))
            ctx["outdoor"] = ranked
        if turn2.calls:
            turns.append(turn2)

    final = _compose_final_answer(user_query, contexts)
    return AgentResponse(final_answer=final, turns=turns, mode="offline-planner")


_MONTHS_TR = {
    1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran",
    7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık",
}

_ACTIVITY_LABELS = {
    "koşu": "Koşu",
    "piknik": "Piknik",
    "fotoğraf": "Fotoğraf çekmek",
    "genel": "Dışarı çıkmak",
}

_VERDICT_PHRASES = {
    "çok uygun": "gayet uygun",
    "uygun": "uygun",
    "koşullu uygun": "kısmen uygun, biraz temkinli olmakta fayda var",
    "uygun değil": "pek uygun değil",
}

_AQI_PHRASES = {
    "çok iyi": "hava son derece temiz",
    "iyi": "hava kalitesi gayet iyi",
    "orta": "hava kalitesi orta düzeyde, hassas gruplar biraz dikkatli olabilir",
    "kötü": "hava kirli, uzun süre dışarıda kalmak pek önerilmez",
    "çok kötü": "hava oldukça kirli, dışarıda geçirilen süreyi kısa tutmakta fayda var",
    "tehlikeli": "hava kalitesi tehlikeli seviyede, mümkünse dışarı çıkmayın",
}


def _round_or_none(value: Any) -> Any:
    return round(value) if isinstance(value, (int, float)) else value


def _format_date_tr(iso_date: str) -> str:
    try:
        _, month, day = iso_date.split("-")
        return f"{int(day)} {_MONTHS_TR[int(month)]}"
    except (ValueError, KeyError):
        return iso_date


def _temp_word(temp: Any) -> str:
    if not isinstance(temp, (int, float)):
        return ""
    if temp < 0:
        return "dondurucu bir soğuk"
    if temp < 8:
        return "oldukça serin"
    if temp < 16:
        return "serin"
    if temp < 24:
        return "ılıman, keyifli bir sıcaklık"
    if temp < 30:
        return "sıcak"
    return "bunaltıcı bir sıcak"


def _wind_word(wind: Any) -> str:
    if not isinstance(wind, (int, float)):
        return ""
    if wind < 8:
        return "sakin"
    if wind < 20:
        return "hafif esintili"
    if wind < 35:
        return "belirgin şekilde rüzgarlı"
    return "oldukça sert rüzgarlı"


def _narrate_forecast(days: list[dict[str, Any]]) -> str:
    if not days:
        return ""
    day_labels = ["Bugün", "Yarın", "Öbür gün"]
    bits: list[str] = []
    for i, day in enumerate(days[:3]):
        label = day_labels[i] if i < len(day_labels) else _format_date_tr(day.get("date", ""))
        tmin = _round_or_none(day.get("temp_min_c"))
        tmax = _round_or_none(day.get("temp_max_c"))
        prob = day.get("precip_probability_pct") or 0
        piece = f"{label} {day.get('condition')}, {tmin}-{tmax}°C"
        if prob and prob >= 30:
            piece += f", yağış ihtimali %{prob}"
        bits.append(piece)
    return "Önümüzdeki günlere bakılırsa: " + "; ".join(bits) + "."


def _narrate_place(ctx: dict[str, Any]) -> str:
    loc = ctx["location"]
    snap = ctx["snapshot"]
    name = loc.get("name") or ctx["place"]

    temp = snap.get("temperature_c")
    feels = snap.get("feels_like_c")
    wind = snap.get("wind_kmh")
    humidity = snap.get("humidity_pct")

    sentence = (
        f"{name}{_locative_suffix(name)} şu anda hava {snap.get('condition')}, sıcaklık "
        f"{_round_or_none(temp)}°C civarında"
    )
    temp_word = _temp_word(temp)
    sentence += f" ve {temp_word} diyebiliriz." if temp_word else "."

    parts = [sentence]

    if isinstance(temp, (int, float)) and isinstance(feels, (int, float)) and abs(feels - temp) >= 2:
        parts.append(f"Hissedilen sıcaklık ise {_round_or_none(feels)}°C.")

    if isinstance(wind, (int, float)):
        parts.append(f"Rüzgar {_wind_word(wind)} ({_round_or_none(wind)} km/h).")

    if isinstance(humidity, (int, float)) and (humidity >= 80 or humidity <= 25):
        hum_word = "oldukça nemli" if humidity >= 80 else "oldukça kuru"
        parts.append(f"Hava {hum_word} (%{humidity}).")

    air = ctx.get("air")
    if air and not air.get("error"):
        aqi_phrase = _AQI_PHRASES.get(air.get("category"), "hava kalitesi hakkında net bir veri yok")
        parts.append(f"{aqi_phrase.capitalize()} (AQI {air.get('european_aqi')}).")

    forecast = ctx.get("forecast")
    if forecast and not forecast.get("error"):
        narration = _narrate_forecast(forecast.get("days") or [])
        if narration:
            parts.append(narration)

    outdoor = ctx.get("outdoor")
    if outdoor and not outdoor.get("error"):
        activity_word = _ACTIVITY_LABELS.get(outdoor.get("activity"), "Bu aktivite")
        verdict_phrase = _VERDICT_PHRASES.get(outdoor.get("verdict"), outdoor.get("verdict"))
        parts.append(
            f"{activity_word} için bu hava {verdict_phrase} (puan: {outdoor.get('score')}/100)."
        )
        notes = outdoor.get("notes") or []
        if notes:
            parts.append(" ".join(notes))

    return " ".join(parts)


def _narrate_comparison(usable: list[dict[str, Any]]) -> str:
    temps = [
        (ctx["location"].get("name") or ctx["place"], ctx["snapshot"]["temperature_c"])
        for ctx in usable
        if isinstance(ctx.get("snapshot", {}).get("temperature_c"), (int, float))
    ]
    if len(temps) < 2:
        return ""

    ordered = sorted(temps, key=lambda x: x[1], reverse=True)
    hottest, hottest_t = ordered[0]
    coldest, coldest_t = ordered[-1]
    if hottest == coldest:
        return ""

    diff = round(hottest_t - coldest_t)
    if diff <= 0:
        return f"Şu anda {hottest} ile {coldest} neredeyse aynı sıcaklıkta."
    return (
        f"Şu anda en sıcak yer {hottest} ({_round_or_none(hottest_t)}°C), en serin ise "
        f"{coldest} ({_round_or_none(coldest_t)}°C) — aralarında yaklaşık {diff} derece fark var."
    )


def _compose_final_answer(query: str, contexts: list[dict[str, Any]]) -> str:
    usable = [
        ctx for ctx in contexts
        if not ctx.get("error") and ctx.get("snapshot") and not ctx["snapshot"].get("error")
    ]

    chunks = [_narrate_place(ctx) for ctx in usable]

    if len(usable) >= 2:
        comparison = _narrate_comparison(usable)
        if comparison:
            chunks.append(comparison)

    if not chunks:
        failed = [ctx for ctx in contexts if ctx.get("error")]
        if failed:
            return (
                "Hangi şehri kastettiğini tam anlayamadım. Şehir adını biraz daha açık "
                "yazabilir misin? Örneğin: İstanbul, Tokyo, Berlin."
            )
        return "Bu soruya cevap verebilecek kadar veri toplayamadım, biraz daha netleştirebilir misin?"
    return "\n\n".join(chunks)


def _groq_available() -> bool:
    return bool(os.getenv("GROQ_API_KEY"))


def run_llm_agent(user_query: str, max_rounds: int = 4) -> AgentResponse:
    """Optional Groq-powered tool calling loop (OpenAI-compatible)."""
    from openai import OpenAI

    client = OpenAI(
        api_key=os.environ["GROQ_API_KEY"],
        base_url="https://api.groq.com/openai/v1",
    )
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_query},
    ]

    turns: list[AgentTurn] = []
    for round_idx in range(1, max_rounds + 1):
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
            temperature=0.2,
        )
        message = completion.choices[0].message
        tool_calls = message.tool_calls or []

        if not tool_calls:
            answer = (message.content or "").strip()
            if not answer:
                answer = "Model nihai bir yanıt üretmedi."
            return AgentResponse(final_answer=answer, turns=turns, mode=f"groq:{model}")

        turn = AgentTurn(index=round_idx)
        messages.append(
            {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            }
        )

        for tc in tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = dispatch_tool(tc.function.name, args)
            turn.calls.append(ToolCall(tc.function.name, args, result))
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.function.name,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )
        turns.append(turn)

    # Force a closing answer if the model keeps calling tools
    messages.append(
        {
            "role": "user",
            "content": "Araç çağrılarını bitir ve Türkçe nihai yanıtı ver.",
        }
    )
    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.2,
    )
    answer = (completion.choices[0].message.content or "").strip()
    return AgentResponse(final_answer=answer, turns=turns, mode=f"groq:{model}")


def run_agent(user_query: str) -> AgentResponse:
    query = (user_query or "").strip()
    if not query:
        return AgentResponse(
            final_answer=(
                "Bir şey yazmamışsın gibi görünüyor. Bir şehir adıyla ya da "
                "'X ile Y' karşılaştırmasıyla deneyebilirsin."
            ),
            turns=[],
            mode="idle",
        )

    if _groq_available():
        try:
            return run_llm_agent(query)
        except Exception as exc:  # noqa: BLE001
            offline = run_offline_agent(query)
            offline.final_answer = (
                f"(LLM hatası nedeniyle çevrimdışı planlayıcı kullanıldı: {exc})\n\n"
                + offline.final_answer
            )
            offline.mode = "offline-fallback"
            return offline

    return run_offline_agent(query)
