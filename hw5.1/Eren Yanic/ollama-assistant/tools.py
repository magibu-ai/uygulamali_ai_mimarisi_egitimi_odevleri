"""The eight tools the model can call, and the schemas that describe them to it.

Two rules hold throughout:

  * a tool returns TEXT and never raises — a failure comes back as a sentence the model
    can read and react to, so one dead API cannot end the conversation;
  * the text is short. Everything the model reads costs context, and there are only
    8192 tokens to spend, so every result is clipped to MAX_TOOL_CHARS.

The schemas are written for a 4B model: terse descriptions, enums instead of free text,
and boundaries stated explicitly where two tools could otherwise be confused.
"""

from __future__ import annotations

import ast
import html
import math
import operator
import os
import re
import resource
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests

import config
import portfolio
from mcp_client import MCPClient, MCPError

USER_AGENT = "ollama-assistant/1.0"

# chat.py installs a callback here so run_python can ask before it runs anything.
confirm_python: "callable[[str], bool] | None" = None

_mcp = MCPClient()

# Quotes are asked for repeatedly — valuing a five-line portfolio is five calls, and
# people re-ask. A short memory keeps the answers consistent within a turn and takes
# load off a server that sleeps when idle.
_mcp_cache: dict[str, tuple[float, str]] = {}


def _mcp_call(name: str, arguments: dict) -> str:
    key = f"{name}:{sorted(arguments.items())}"
    hit = _mcp_cache.get(key)
    if hit and time.time() - hit[0] < config.MCP_CACHE_TTL:
        return hit[1]
    result = _mcp.call_tool(name, arguments)
    _mcp_cache[key] = (time.time(), result)
    return result


def _clip(text: str, limit: int | None = None) -> str:
    limit = limit or config.MAX_TOOL_CHARS
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... [truncated, {len(text) - limit} more characters]"


def _get(url: str, **params) -> dict:
    response = requests.get(
        url, params=params, headers={"User-Agent": USER_AGENT}, timeout=config.HTTP_TIMEOUT
    )
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------- web search
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web with Tavily, falling back to DuckDuckGo when there is no key."""
    max_results = max(1, min(int(max_results), 8))
    if not config.TAVILY_KEY:
        return _duckduckgo(query, max_results)
    try:
        response = requests.post(
            "https://api.tavily.com/search",
            # The key travels in the header, never in the body we might log.
            headers={"Authorization": f"Bearer {config.TAVILY_KEY}", "User-Agent": USER_AGENT},
            json={
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
                "include_answer": True,
            },
            timeout=config.HTTP_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        return _duckduckgo(query, max_results)

    lines = []
    if data.get("answer"):
        lines.append(f"Summary: {data['answer']}")
    for index, item in enumerate(data.get("results", [])[:max_results], start=1):
        snippet = " ".join((item.get("content") or "").split())[:280]
        lines.append(f"{index}. {item.get('title', '')}\n   {snippet}\n   {item.get('url', '')}")
    return _clip("\n".join(lines) or f"No results for '{query}'.")


def _duckduckgo(query: str, max_results: int) -> str:
    """Keyless fallback: DuckDuckGo's lite endpoint, scraped."""
    try:
        response = requests.post(
            "https://lite.duckduckgo.com/lite/",
            data={"q": query},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=config.HTTP_TIMEOUT,
        )
        pairs = re.findall(
            r"""<a[^>]*href="([^"]+)"[^>]*class=['"]result-link['"][^>]*>(.*?)</a>""",
            response.text, flags=re.DOTALL,
        )
    except requests.RequestException as exc:
        return f"Search failed: {exc}"

    lines = []
    for url, raw_title in pairs[:max_results]:
        title = html.unescape(re.sub(r"<[^>]+>", "", raw_title)).strip()
        if title:
            lines.append(f"{len(lines) + 1}. {title}\n   {html.unescape(url)}")
    return _clip("\n".join(lines) or f"No results for '{query}'.")


# ------------------------------------------------------------------ date and time
# Enough cities to answer the common question offline; anything else is geocoded.
CITY_ZONES = {
    "istanbul": "Europe/Istanbul", "ankara": "Europe/Istanbul", "izmir": "Europe/Istanbul",
    "antalya": "Europe/Istanbul", "bursa": "Europe/Istanbul", "turkey": "Europe/Istanbul",
    "turkiye": "Europe/Istanbul", "london": "Europe/London", "paris": "Europe/Paris",
    "berlin": "Europe/Berlin", "madrid": "Europe/Madrid", "rome": "Europe/Rome",
    "amsterdam": "Europe/Amsterdam", "moscow": "Europe/Moscow", "kyiv": "Europe/Kyiv",
    "athens": "Europe/Athens", "zurich": "Europe/Zurich", "stockholm": "Europe/Stockholm",
    "new york": "America/New_York", "washington": "America/New_York",
    "los angeles": "America/Los_Angeles", "san francisco": "America/Los_Angeles",
    "chicago": "America/Chicago", "toronto": "America/Toronto",
    "mexico city": "America/Mexico_City", "sao paulo": "America/Sao_Paulo",
    "tokyo": "Asia/Tokyo", "seoul": "Asia/Seoul", "beijing": "Asia/Shanghai",
    "shanghai": "Asia/Shanghai", "hong kong": "Asia/Hong_Kong", "singapore": "Asia/Singapore",
    "dubai": "Asia/Dubai", "doha": "Asia/Qatar", "riyadh": "Asia/Riyadh",
    "tehran": "Asia/Tehran", "baku": "Asia/Baku", "delhi": "Asia/Kolkata",
    "mumbai": "Asia/Kolkata", "jakarta": "Asia/Jakarta", "bangkok": "Asia/Bangkok",
    "sydney": "Australia/Sydney", "melbourne": "Australia/Melbourne",
    "auckland": "Pacific/Auckland", "cairo": "Africa/Cairo", "lagos": "Africa/Lagos",
    "johannesburg": "Africa/Johannesburg", "nairobi": "Africa/Nairobi", "utc": "UTC",
}

# Turkish spellings reach us as typed; fold them to the ASCII keys above.
_TR_FOLD = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def get_datetime(location: str = "") -> str:
    """Current date and time, here or in any city in the world."""
    place = (location or "").strip()
    if not place:
        now = datetime.now().astimezone()
        return f"Local time: {now:%Y-%m-%d %H:%M} ({now:%A}, UTC{now:%z})"

    key = place.translate(_TR_FOLD).lower()
    zone_name = CITY_ZONES.get(key)

    if zone_name is None and "/" in place:
        zone_name = place  # already an IANA name such as Europe/Istanbul

    if zone_name is None:  # unknown city: ask the geocoder, which knows time zones
        try:
            results = _get(
                "https://geocoding-api.open-meteo.com/v1/search", name=place, count=1
            ).get("results")
            if not results:
                return f"I could not find a place called '{place}'."
            zone_name = results[0].get("timezone")
            place = results[0].get("name", place)
        except requests.RequestException as exc:
            return f"Could not look up the time zone for '{place}': {exc}"

    try:
        now = datetime.now(ZoneInfo(zone_name))
    except (ZoneInfoNotFoundError, ValueError):
        return f"'{zone_name}' is not a known time zone."
    return f"{place} ({zone_name}): {now:%Y-%m-%d %H:%M} ({now:%A}, UTC{now:%z})"


# ---------------------------------------------------------------------- weather
WMO_CODES = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "rime fog", 51: "light drizzle", 53: "drizzle",
    55: "dense drizzle", 56: "freezing drizzle", 57: "dense freezing drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain",
    67: "heavy freezing rain", 71: "light snow", 73: "snow", 75: "heavy snow",
    77: "snow grains", 80: "light showers", 81: "showers", 82: "violent showers",
    85: "snow showers", 86: "heavy snow showers", 95: "thunderstorm",
    96: "thunderstorm with hail", 99: "thunderstorm with heavy hail",
}


def get_weather(location: str) -> str:
    """Current conditions plus today's range for a city. No API key needed."""
    try:
        places = _get(
            "https://geocoding-api.open-meteo.com/v1/search", name=location, count=1
        ).get("results")
        if not places:
            return f"I could not find a place called '{location}'."
        place = places[0]

        data = _get(
            "https://api.open-meteo.com/v1/forecast",
            latitude=place["latitude"], longitude=place["longitude"],
            current="temperature_2m,apparent_temperature,relative_humidity_2m,"
                    "wind_speed_10m,weather_code",
            daily="temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            timezone="auto", forecast_days=1,
        )
    except (requests.RequestException, KeyError) as exc:
        return f"Could not fetch the weather: {exc}"

    now, daily = data["current"], data["daily"]
    return (
        f"{place['name']}, {place.get('country', '')}: "
        f"{WMO_CODES.get(now['weather_code'], 'unknown')}, {now['temperature_2m']}°C "
        f"(feels like {now['apparent_temperature']}°C), humidity {now['relative_humidity_2m']}%, "
        f"wind {now['wind_speed_10m']} km/h. "
        f"Today {daily['temperature_2m_min'][0]}–{daily['temperature_2m_max'][0]}°C, "
        f"chance of precipitation {daily['precipitation_probability_max'][0]}%. "
        f"(local time {now['time']})"
    )


# --------------------------------------------------------------------- currency
COIN_IDS = {
    "BTC": "bitcoin", "ETH": "ethereum", "USDT": "tether", "USDC": "usd-coin",
    "BNB": "binancecoin", "XRP": "ripple", "SOL": "solana", "ADA": "cardano",
    "DOGE": "dogecoin", "TRX": "tron", "AVAX": "avalanche-2", "DOT": "polkadot",
    "LINK": "chainlink", "MATIC": "matic-network", "LTC": "litecoin",
    "SHIB": "shiba-inu", "TON": "the-open-network", "XMR": "monero",
    "ATOM": "cosmos", "UNI": "uniswap", "PEPE": "pepe", "XLM": "stellar",
}


def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    """Convert between currencies, crypto included."""
    source = from_currency.strip().upper()
    target = to_currency.strip().upper()
    amount = float(amount)
    if source == target:
        return f"{amount:g} {source} = {amount:g} {target}"

    try:
        if source in COIN_IDS or target in COIN_IDS:
            rate, note = _crypto_rate(source, target)
        else:
            rate, note = _fiat_rate(source, target)
    except requests.RequestException as exc:
        return f"Could not fetch the rate: {exc}"
    if rate is None:
        return note
    return f"{amount:g} {source} = {amount * rate:,.4f} {target} (1 {source} = {rate:,.6g} {target}). {note}"


def _fiat_rate(source: str, target: str) -> tuple[float | None, str]:
    """Frankfurter first; a second free source covers its outages and timeouts."""
    try:
        data = _get("https://api.frankfurter.dev/v1/latest", base=source, symbols=target)
        rate = data.get("rates", {}).get(target)
        if rate is not None:
            return rate, f"Reference rate published {data['date']} (daily, not intraday)."
    except requests.RequestException:
        pass  # unknown code (404) or a slow day — either way, try the other source

    try:
        data = _get(f"https://open.er-api.com/v6/latest/{source}")
        rate = (data.get("rates") or {}).get(target)
        if rate is not None:
            return rate, f"Rate from open.er-api.com ({data.get('time_last_update_utc', '')[:16]})."
    except requests.RequestException:
        pass

    return None, (
        f"No {source}/{target} rate available from either source. Major currencies "
        f"(USD, EUR, TRY, GBP) are covered. For gold, silver or oil use the borsa tool "
        f"with market='fx' and symbol='gram-altin'."
    )


def _crypto_rate(source: str, target: str) -> tuple[float | None, str]:
    """CoinGecko spot. Crypto-to-crypto goes through USD."""
    if source in COIN_IDS and target in COIN_IDS:
        data = _get(
            "https://api.coingecko.com/api/v3/simple/price",
            ids=f"{COIN_IDS[source]},{COIN_IDS[target]}", vs_currencies="usd",
        )
        source_usd = data.get(COIN_IDS[source], {}).get("usd")
        target_usd = data.get(COIN_IDS[target], {}).get("usd")
        if not source_usd or not target_usd:
            return None, f"No spot price for {source} or {target}."
        return source_usd / target_usd, "Spot price via CoinGecko (crossed through USD)."

    coin, fiat, inverted = (
        (source, target, False) if source in COIN_IDS else (target, source, True)
    )
    data = _get(
        "https://api.coingecko.com/api/v3/simple/price",
        ids=COIN_IDS[coin], vs_currencies=fiat.lower(),
    )
    price = data.get(COIN_IDS[coin], {}).get(fiat.lower())
    if not price:
        return None, f"CoinGecko has no {coin} price in {fiat}."
    return (1 / price if inverted else price), "Spot price via CoinGecko."


# -------------------------------------------------------------------- calculator
# An allow-list evaluator: the model's expression is parsed, and any node that is not
# arithmetic is rejected. Nothing is executed, so there is no path to imports or files.
_OPERATORS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos,
}
_FUNCTIONS = {
    name: getattr(math, name) for name in (
        "sqrt", "log", "log2", "log10", "exp", "sin", "cos", "tan", "asin", "acos",
        "atan", "floor", "ceil", "fabs", "factorial", "degrees", "radians", "hypot",
    )
}
_FUNCTIONS.update(abs=abs, round=round, min=min, max=max, sum=sum, pow=pow)
_CONSTANTS = {"pi": math.pi, "e": math.e, "tau": math.tau}


def _evaluate(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_evaluate(node.left), _evaluate(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_evaluate(node.operand))
    if isinstance(node, ast.Name) and node.id in _CONSTANTS:
        return _CONSTANTS[node.id]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id not in _FUNCTIONS:
            raise ValueError(f"'{node.func.id}' is not an allowed function")
        return _FUNCTIONS[node.func.id](*[_evaluate(arg) for arg in node.args])
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_evaluate(item) for item in node.elts]
    raise ValueError("only arithmetic is allowed here")


def calculate(expression: str) -> str:
    """Evaluate one arithmetic expression, exactly."""
    cleaned = expression.strip().rstrip("=").replace("^", "**").replace(",", "")
    try:
        result = _evaluate(ast.parse(cleaned, mode="eval").body)
    except ZeroDivisionError:
        return "Division by zero."
    except (ValueError, SyntaxError, TypeError, OverflowError) as exc:
        return f"Could not evaluate '{expression}': {exc}"
    if isinstance(result, float) and result.is_integer() and abs(result) < 1e15:
        result = int(result)
    return f"{cleaned} = {result}"


# ---------------------------------------------------------------- code execution
_PYTHON_PREAMBLE = "Only the standard library is available. Print what you want to see.\n"


def _repair_indentation(code: str) -> str:
    """Undo the stray leading space small models put on continuation lines.

    They emit "import x\\n y = 1", which is an IndentationError. Stripping a common
    indent blindly would break genuinely indented code, so the compiler decides: only
    code that does not parse is touched, and only if the repair makes it parse.
    """
    try:
        compile(code, "<model>", "exec")
        return code
    except IndentationError:
        pass
    except SyntaxError:
        return code  # a real syntax error; let the traceback explain it

    lines = code.splitlines()
    indents = [len(line) - len(line.lstrip(" ")) for line in lines[1:] if line.strip()]
    if not indents or not min(indents):
        return code
    shift = min(indents)
    repaired = "\n".join(
        [lines[0]] + [line[shift:] if line.strip() else line for line in lines[1:]]
    )
    try:
        compile(repaired, "<model>", "exec")
    except SyntaxError:
        return code
    return repaired


def run_python(code: str) -> str:
    """Run model-written Python in a throwaway sandbox and return what it printed."""
    code = _repair_indentation(code)
    if config.CONFIRM_PYTHON:
        if confirm_python is None:
            return "Code execution is not available in this session."
        if not confirm_python(code):
            return ("The user declined to run this code. Do NOT work the answer out "
                    "yourself - say plainly that you cannot answer without running it, "
                    "and offer a different approach.")

    def _limits() -> None:  # applied inside the child, before exec
        resource.setrlimit(resource.RLIMIT_AS,
                           (config.PYTHON_MEM_MB * 1024 * 1024,) * 2)
        resource.setrlimit(resource.RLIMIT_CPU, (config.PYTHON_TIMEOUT, config.PYTHON_TIMEOUT))
        resource.setrlimit(resource.RLIMIT_FSIZE, (5 * 1024 * 1024,) * 2)
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))

    with tempfile.TemporaryDirectory(prefix="assistant-py-") as workspace:
        try:
            completed = subprocess.run(
                [sys.executable, "-I", "-c", code],
                cwd=workspace,          # a directory that disappears afterwards
                # A deliberately bare environment: the parent's variables, API keys
                # included, must not be visible to code the model wrote.
                env={"PATH": "/usr/bin:/bin", "HOME": workspace,
                     "LANG": os.environ.get("LANG", "C.UTF-8")},
                capture_output=True, text=True, timeout=config.PYTHON_TIMEOUT,
                preexec_fn=_limits,
            )
        except subprocess.TimeoutExpired:
            return f"The code ran longer than {config.PYTHON_TIMEOUT} s and was stopped."
        except OSError as exc:
            return f"Could not start the interpreter: {exc}"

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    if completed.returncode != 0:
        last_line = stderr.splitlines()[-1] if stderr else "no message"
        return _clip(f"The code failed: {last_line}\n{stderr}", 1200)
    if not stdout:
        return "The code ran without errors but printed nothing. " + _PYTHON_PREAMBLE
    return _clip(stdout, config.PYTHON_MAX_OUTPUT)


# --------------------------------------------------------------- market data (MCP)
# One tool over seven remote ones. The server offers 23; naming them all would cost
# thousands of tokens of schema and leave a 4B model guessing between near-identical
# options. The action enum below is the curated subset, mapped to real calls here.
_FIAT = {
    "USD", "EUR", "TRY", "GBP", "CHF", "JPY", "SAR", "RUB", "CNY", "AUD", "CAD",
    "SEK", "NOK", "DKK", "PLN", "AED", "KWD", "QAR", "ILS", "INR", "KRW", "BRL",
    "MXN", "ZAR", "CZK", "HUF", "RON", "BGN", "NZD", "SGD", "HKD",
}
_MARKET_SYMBOLS = _FIAT | {
    "GRAM-ALTIN", "ONS-ALTIN", "CEYREK-ALTIN", "TAM-ALTIN", "GUMUS", "BRENT", "WTI",
}
_ACTION_MARKETS = {  # markets each remote tool actually accepts
    "search": {"bist", "us", "crypto", "fx", "fund"},
    "quote": {"bist", "us", "fx", "crypto"},
    "history": {"bist", "us", "fx", "crypto", "fund"},
    "technical": {"bist", "us", "crypto"},
    "index": {"bist", "us"},
}


def _infer_market(symbol: str) -> str:
    """Guess the market when the model omits it, so a good query is not wasted."""
    upper = symbol.strip().upper()
    if upper in _MARKET_SYMBOLS or upper.endswith("-ALTIN"):
        return "fx"
    if upper in COIN_IDS or "-USD" in upper or upper.endswith("USDT") or (
        len(upper) > 4 and upper.endswith("TRY") and upper[:-3] in COIN_IDS
    ):
        return "crypto"
    return "bist"  # a Turkey-first assistant; the US fallback below covers the rest


def _normalize(symbol: str, market: str) -> str:
    """Turn a bare coin name into a tradeable pair: 'BTC' on its own cannot be priced."""
    upper = symbol.strip().upper()
    if market == "crypto" and upper in COIN_IDS:
        return f"{upper}TRY"  # BtcTurk quotes in lira, which is what a user here wants
    return symbol.strip()


def borsa(action: str, symbol: str = "", market: str = "", period: str = "") -> str:
    """Bridge to the Borsa MCP server: BIST and US stocks, funds, indices, FX, crypto."""
    action = (action or "").strip().lower()
    symbol = (symbol or "").strip()
    market = (market or "").strip().lower()

    if action not in {"search", "quote", "history", "technical", "index", "fund", "news"}:
        return (f"Unknown action '{action}'. Use one of: search, quote, history, "
                f"technical, index, fund, news.")
    if not symbol:
        return f"The '{action}' action needs a symbol, for example 'THYAO' or 'AAPL'."

    # "USDTRY" is a currency pair, not a listed security. Left alone it resolves to some
    # unrelated ticker and returns a number that reads like an exchange rate but is not
    # one. Send the model to the tool that actually answers the question.
    plain = re.sub(r"[/\-_= ]", "", symbol).upper()
    if len(plain) == 6 and plain[:3] in _FIAT and plain[3:] in _FIAT:
        return (f"{symbol} is a currency pair, not a share. Use convert_currency with "
                f"amount=1, from_currency={plain[:3]}, to_currency={plain[3:]}.")

    inferred = not market
    if inferred:
        market = _infer_market(symbol)
    # "USD" is also a real US ETF ticker, so asking the US market for it returns a share
    # price near $28 that reads exactly like an exchange rate. In an assistant about
    # Turkish money, a currency code means the currency — always.
    if symbol.strip().upper() in _MARKET_SYMBOLS and action in {"quote", "history"}:
        market, inferred = "fx", False
    allowed = _ACTION_MARKETS.get(action)
    if allowed and market not in allowed:
        market = "bist" if "bist" in allowed else sorted(allowed)[0]
    if action != "search":
        symbol = _normalize(symbol, market)

    name, arguments = _mcp_call_for(action, symbol, market, period)
    try:
        result = _mcp_call(name, arguments)
        # BIST is the default guess; if nothing came back, the symbol is probably American.
        if inferred and market == "bist" and _looks_empty(result) and action != "fund":
            arguments["market"] = "us"
            result = _mcp_call(name, arguments)
    except MCPError as exc:
        return f"Market data unavailable: {exc}"
    if action == "quote":
        result = _with_lira_equivalent(result)
    return _clip(result)


def _with_lira_equivalent(text: str) -> str:
    """Attach the lira value of a foreign-currency quote, computed here.

    Asked what Apple costs in lira, the model would fetch the dollar price and then
    multiply by a rate it made up - 3.10 in one run, 4.52 in another, and 47.757 with
    an arithmetic slip once it had seen the real figure. Chaining to convert_currency is
    what it should do, and prompting did not reliably get it there. So the tool answers
    the whole question itself: exact arithmetic, no second call, nothing left to invent.
    """
    currency = re.search(r"^currency:\s*([A-Za-z]{3})\s*$", text, re.MULTILINE)
    price = re.search(r"^current_price:\s*([0-9]*\.?[0-9]+)\s*$", text, re.MULTILINE)
    if not currency or not price or currency.group(1).upper() == "TRY":
        return text
    rate, _ = _fiat_rate(currency.group(1).upper(), "TRY")
    if not rate:
        return text
    return (f"{text}\nprice_in_try: {float(price.group(1)) * rate:,.2f}  "
            f"(1 {currency.group(1).upper()} = {rate:,.4f} TRY, converted by this tool)")


def warm_market_data() -> bool:
    """Wake the market server in the background so the first question is not slow."""
    return _mcp.warm()


def _mcp_call_for(action: str, symbol: str, market: str, period: str) -> tuple[str, dict]:
    if action == "search":
        return "search_symbol", {"query": symbol, "market": market, "limit": 8}
    if action == "quote":
        return "get_quote", {"symbol": symbol, "market": market}
    if action == "history":
        valid = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "ytd", "max"}
        return "get_historical_data", {
            "symbol": symbol, "market": market,
            "period": period if period in valid else "1mo",
        }
    if action == "technical":
        return "get_technical_analysis", {"symbol": symbol, "market": market, "timeframe": "1d"}
    if action == "index":
        return "get_index_data", {"code": symbol, "market": market}
    if action == "fund":
        return "get_fund_data", {"symbol": symbol, "include_performance": True}
    return "get_news", {"symbol": symbol, "limit": 5}


def _looks_empty(result: str) -> bool:
    return "failed_count: 1" in result or "successful_count: 0" in result or not result.strip()


_PRICE_KEYS = ("current_price", "price", "last", "close", "nav")


def _price_lookup(symbol: str, market: str) -> tuple[float, str] | None:
    """What one unit of this asset is worth, for portfolio valuation."""
    try:
        if market == "fund":
            text = _mcp_call("get_fund_data", {"symbol": symbol})
        else:
            text = _mcp_call("get_quote", {"symbol": symbol, "market": market})
    except MCPError:
        return None

    price = None
    for key in _PRICE_KEYS:
        match = re.search(rf"^{key}:\s*([0-9]*\.?[0-9]+)\s*$", text, re.MULTILINE)
        if match:
            price = float(match.group(1))
            break
    if price is None:
        return None

    currency_match = re.search(r"^currency:\s*([A-Za-z]{3})\s*$", text, re.MULTILINE)
    if currency_match:
        currency = currency_match.group(1).upper()
    elif market == "crypto":
        currency = "USD" if "-USD" in symbol.upper() else "TRY"
    else:
        currency = "TRY"  # BIST, TEFAS funds and the borsapy FX quotes are all TRY
    return price, currency


# ----------------------------------------------------------- portfolio (scenario)
def portfolio_tool(action: str, symbol: str = "", market: str = "",
                   quantity: float | None = None, cost: float | None = None) -> str:
    """Read and write the local holdings ledger."""
    action = (action or "").strip().lower()
    if action == "list":
        return portfolio.listing()
    if action == "value":
        return _clip(portfolio.valuation(_price_lookup))
    if action == "add":
        if not symbol or quantity is None:
            return "To add a position I need a symbol and a quantity."
        market = market or _infer_market(symbol)
        # A cost of zero means the model had none to report, not a free share.
        return portfolio.add(_normalize(symbol, market), market, float(quantity),
                             cost if cost else None)
    if action == "remove":
        if not symbol:
            return "To remove a position I need a symbol."
        quantity = None if quantity is None else float(quantity)
        result = portfolio.remove(symbol, quantity)
        if "not in the portfolio" in result and _normalize(symbol, "crypto") != symbol:
            return portfolio.remove(_normalize(symbol, "crypto"), quantity)  # "sell my BTC"
        return result
    return f"Unknown action '{action}'. Use: add, remove, list or value."


# ------------------------------------------------------------------- registration
TOOLS = {
    "web_search": web_search,
    "get_datetime": get_datetime,
    "get_weather": get_weather,
    "convert_currency": convert_currency,
    "calculate": calculate,
    "run_python": run_python,
    "borsa": borsa,
    "portfolio": portfolio_tool,
}


def _schema(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties, "required": required},
    }}


TOOL_SCHEMAS = [
    _schema(
        "web_search",
        "Search the web for news, current events, or facts you do not know. "
        "Not for prices or market data — use borsa for those.",
        {"query": {"type": "string",
                   "description": "Search keywords. Write them in the language of the "
                                  "likely source; keep them short and specific."},
         "max_results": {"type": "integer",
                         "description": "How many results, 1-8. Leave it out to get 5; "
                                        "one result is rarely enough."}},
        ["query"],
    ),
    _schema(
        "get_datetime",
        "The current date and time. Give a city to get its local time.",
        {"location": {"type": "string",
                      "description": "City or IANA zone, e.g. 'Tokyo'. Omit for local time."}},
        [],
    ),
    _schema(
        "get_weather",
        "Current weather and today's temperature range for a city.",
        {"location": {"type": "string", "description": "City name, e.g. 'Istanbul'."}},
        ["location"],
    ),
    _schema(
        "convert_currency",
        "Convert an amount from one currency to another. Handles fiat (USD, EUR, TRY) "
        "and crypto (BTC, ETH). Use this for 'how much is X in Y', not for gold or shares.",
        {"amount": {"type": "number", "description": "How much to convert."},
         "from_currency": {"type": "string", "description": "Source code, e.g. USD or BTC."},
         "to_currency": {"type": "string", "description": "Target code, e.g. TRY."}},
        ["amount", "from_currency", "to_currency"],
    ),
    _schema(
        "calculate",
        "Evaluate one arithmetic expression exactly. Use it for every calculation "
        "instead of working the answer out yourself.",
        {"expression": {"type": "string",
                        "description": "e.g. '(1250 * 1.2) / 3' or 'sqrt(2) * 100'."}},
        ["expression"],
    ),
    _schema(
        "run_python",
        "Run a short Python program when a task needs logic, loops or dates rather than "
        "a single expression. Standard library only, and it must print its result.",
        {"code": {"type": "string", "description": "Complete Python source that prints output."}},
        ["code"],
    ),
    _schema(
        "borsa",
        "Turkish and US market data: share prices, indices (XU100), TEFAS funds, gold, "
        "oil and crypto. Also company news from KAP.",
        {"action": {"type": "string",
                    "enum": ["search", "quote", "history", "technical", "index", "fund", "news"],
                    "description": "quote=current price, search=find a ticker by name, "
                                   "history=past prices, technical=RSI/MACD, "
                                   "index=XU100 or SPY, fund=TEFAS fund, news=KAP filings."},
         "symbol": {"type": "string",
                    "description": "Ticker or search term: THYAO, AAPL, XU100, BTCTRY, "
                                   "gram-altin, or a fund code such as TPC."},
         "market": {"type": "string", "enum": ["bist", "us", "crypto", "fx", "fund"],
                    "description": "bist=Turkish shares, us=US shares, fx=currency/gold/oil. "
                                   "Omit it and it will be inferred."},
         "period": {"type": "string",
                    "description": "For history only: 1d, 5d, 1mo, 3mo, 6mo, 1y, 5y, ytd."}},
        ["action", "symbol"],
    ),
    _schema(
        "portfolio",
        "The user's own holdings, stored privately on this machine. Use it whenever they "
        "say 'my portfolio', 'my shares', or ask what they own or what it is worth.",
        {"action": {"type": "string", "enum": ["add", "remove", "list", "value"],
                    "description": "add=buy, remove=sell, list=show holdings, "
                                   "value=price everything at today's market."},
         "symbol": {"type": "string", "description": "Ticker, e.g. THYAO or BTCTRY."},
         "market": {"type": "string", "enum": ["bist", "us", "crypto", "fx", "fund"],
                    "description": "Where it trades. Omit it and it will be inferred."},
         "quantity": {"type": "number", "description": "Number of units bought or sold."},
         "cost": {"type": "number",
                  "description": "Price paid per unit. Include this ONLY if the user "
                                 "stated it. Never estimate it, never use today's price. "
                                 "Leave it out when they did not say."}},
        ["action"],
    ),
]

# Parameter types, taken straight from the schemas above, used to coerce what the model
# sends: small models routinely pass "10" where a number belongs.
_PARAM_TYPES = {
    schema["function"]["name"]: {
        key: value.get("type")
        for key, value in schema["function"]["parameters"]["properties"].items()
    }
    for schema in TOOL_SCHEMAS
}


def _coerce(name: str, arguments: dict) -> dict:
    types = _PARAM_TYPES[name]
    cleaned = {}
    for key, value in arguments.items():
        if key not in types or value is None or value == "":
            continue  # silently drop invented parameters
        try:
            if types[key] == "number":
                cleaned[key] = float(str(value).replace(",", ""))
            elif types[key] == "integer":
                cleaned[key] = int(float(str(value)))
            elif types[key] == "string":
                cleaned[key] = str(value)
            else:
                cleaned[key] = value
        except (TypeError, ValueError):
            continue
    return cleaned


def run(name: str, arguments: dict) -> str:
    """Dispatch one tool call. Always returns text, whatever happens."""
    function = TOOLS.get(name)
    if function is None:
        return f"There is no tool called '{name}'. Available: {', '.join(TOOLS)}."
    try:
        return function(**_coerce(name, arguments or {}))
    except TypeError as exc:
        # A missing required argument: tell the model plainly so it can call again.
        return f"Wrong arguments for {name}: {exc}"
    except Exception as exc:  # a broken tool must not end the conversation
        return f"{name} failed: {type(exc).__name__}: {config.redact(str(exc))}"
