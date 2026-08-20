"""Exercise every tool directly, without the model.

The language model is the slow, expensive part of this system and the least deterministic.
Everything underneath it can be checked on its own, so it is — against the live APIs, which
is the point: this proves the network paths work, not that a mock does.

    python test_tools.py            # all checks
    python test_tools.py --offline  # only the ones that need no network
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import config

# Point the portfolio at a scratch database before anything opens the real one.
_SCRATCH = tempfile.TemporaryDirectory(prefix="assistant-test-")
config.DATA_DIR = Path(_SCRATCH.name)
config.DB_PATH = config.DATA_DIR / "portfolio.db"

import tools  # noqa: E402  (must follow the redirect above)

PASS, FAIL = "\033[32m✓\033[0m", "\033[31m✗\033[0m"
DIM, RESET = "\033[2m", "\033[0m"
results = {"pass": 0, "fail": 0}


def check(label: str, condition: bool, detail: str = "") -> None:
    key = "pass" if condition else "fail"
    results[key] += 1
    print(f"  {PASS if condition else FAIL} {label}")
    if detail:
        print(f"      {DIM}{' '.join(detail.split())[:150]}{RESET}")


def section(title: str) -> None:
    print(f"\n\033[1m{title}\033[0m")


def offline_checks() -> None:
    section("calculate")
    check("arithmetic", tools.calculate("(1250 * 1.2) / 3") == "(1250 * 1.2) / 3 = 500")
    check("functions and constants", "141" in tools.calculate("sqrt(2) * 100"))
    check("caret means power", tools.calculate("2^10").endswith("= 1024"))
    check("thousands separators tolerated", tools.calculate("1,500 + 500").endswith("= 2000"))
    check("division by zero handled", "zero" in tools.calculate("1/0").lower())
    for hostile in ("__import__('os').system('id')", "open('/etc/passwd').read()", "x := 5"):
        check(f"rejects {hostile[:28]}", "Could not evaluate" in tools.calculate(hostile))

    section("run_python (sandbox)")
    tools.confirm_python = lambda code: True
    check("runs and captures stdout", tools.run_python("print(sum(range(101)))") == "5050")
    check("standard library available",
          "2026" in tools.run_python("import datetime;print(datetime.date(2026,1,1))"))
    check("reports a traceback rather than raising", "failed" in tools.run_python("1/0").lower())
    check("stops an endless loop",
          "stopped" in tools.run_python("while True: pass").lower())
    # Small models emit "import x\n y = 1" — one stray space that will not compile.
    broken = "from datetime import date\n today = date(2026,8,13)\n print(today.year)"
    check("stray indentation repaired", tools.run_python(broken) == "2026")
    upright = "for i in range(3):\n    print(i)"
    check("real indentation left alone", tools._repair_indentation(upright) == upright)
    check("a genuine syntax error is still reported",
          "SyntaxError" in tools.run_python("print(1+)"))

    leak = tools.run_python(
        "import os;print([k for k in os.environ if 'KEY' in k.upper() or 'TOKEN' in k.upper()])"
    )
    check("no API keys reach the sandbox", leak.strip() == "[]", leak)
    check("secrets are redacted from text", "[REDACTED]" in config.redact(
        f"key is {config.TAVILY_KEY or 'tvly-dev-abcdefghijkl'}"))

    tools.confirm_python = lambda code: False
    check("declining stops execution", "declined" in tools.run_python("print(1)"))
    tools.confirm_python = lambda code: True

    section("argument handling")
    # "100" arrives as a string from the model; same-currency short-circuits, no network.
    check("string numbers coerced to float",
          tools.run("convert_currency",
                    {"amount": "100", "from_currency": "usd", "to_currency": "USD"})
          == "100 USD = 100 USD")
    check("invented parameters dropped",
          tools.run("calculate", {"expression": "6*7", "units": "metric"}).endswith("= 42"))
    check("unknown tool reported", "no tool called" in tools.run("get_stock", {}))
    check("missing argument reported", "Wrong arguments" in tools.run("get_weather", {}))

    section("time zones")
    check("local time", "Local time:" in tools.get_datetime())
    check("known city", "Asia/Tokyo" in tools.get_datetime("Tokyo"))
    check("Turkish spelling folded", "Europe/Istanbul" in tools.get_datetime("İstanbul"))
    check("IANA name accepted", "America/New_York" in tools.get_datetime("America/New_York"))

    section("portfolio ledger")
    check("empty at first", "empty" in tools.portfolio_tool("list"))
    tools.portfolio_tool("add", symbol="THYAO", quantity=10, cost=280.0)
    tools.portfolio_tool("add", symbol="THYAO", quantity=10, cost=300.0)
    listing = tools.portfolio_tool("list")
    check("weighted average cost", "290.00" in listing, listing)
    check("market inferred as bist", "(bist)" in listing)
    check("partial sale", "5 left" in tools.portfolio_tool("remove", symbol="THYAO", quantity=15))
    check("full removal", "Removed" in tools.portfolio_tool("remove", symbol="THYAO"))
    check("unknown symbol", "not in the portfolio" in tools.portfolio_tool("remove", symbol="XXX"))
    check("bad action explained", "Unknown action" in tools.portfolio_tool("sell"))

    # "add 0.05 BTC": a bare coin name cannot be priced, so it becomes a traded pair.
    check("bare coin routed to crypto", tools._infer_market("BTC") == "crypto")
    tools.portfolio_tool("add", symbol="BTC", quantity=0.05)
    stored = tools.portfolio_tool("list")
    check("bare coin stored as a pair", "BTCTRY (crypto)" in stored, stored)
    check("a cost of zero is not recorded as a cost", "average cost 0" not in stored)
    check("selling by the short name still works",
          "Removed" in tools.portfolio_tool("remove", symbol="BTC"))


def online_checks() -> None:
    section("weather (Open-Meteo)")
    weather = tools.get_weather("Istanbul")
    check("current conditions", "°C" in weather and "Istanbul" in weather, weather)
    check("unknown place handled", "could not find" in tools.get_weather("Zzzyx").lower())

    section("time zone lookup for an unlisted city")
    lookup = tools.get_datetime("Reykjavik")
    check("geocoded", "Atlantic/Reykjavik" in lookup, lookup)

    section("currency (Frankfurter + CoinGecko)")
    fiat = tools.convert_currency(100, "USD", "TRY")
    check("USD to TRY", "TRY" in fiat and "=" in fiat, fiat)
    crypto = tools.convert_currency(0.5, "BTC", "TRY")
    check("BTC to TRY", "TRY" in crypto and "CoinGecko" in crypto, crypto)
    reverse = tools.convert_currency(1000, "EUR", "ETH")
    check("EUR to ETH", "ETH" in reverse, reverse)
    check("unsupported pair explained", "gram-altin" in tools.convert_currency(1, "XAU", "TRY"))

    section("web search")
    search = tools.web_search("Borsa Istanbul XU100 endeksi", max_results=3)
    check("results returned", len(search) > 80, search)
    check("the API key never appears in the result",
          not config.TAVILY_KEY or config.TAVILY_KEY not in search)

    section("borsa (MCP bridge)")
    quote = tools.borsa("quote", "THYAO")
    check("BIST quote", "current_price" in quote, quote)
    apple = tools.borsa("quote", "AAPL")
    check("US inferred after a BIST miss", "current_price" in apple)
    check("a foreign quote carries its lira value", "price_in_try:" in apple,
          apple.splitlines()[-1])
    check("a lira quote is not converted again", "price_in_try" not in quote)
    check("Turkish characters intact", "Ü" in tools.borsa("search", "Türk Hava Yolları"),
          tools.borsa("search", "Türk Hava Yolları")[:200])
    check("index", "XU100" in tools.borsa("index", "XU100").upper())
    check("gold in TRY", "gram-altin" in tools.borsa("quote", "gram-altin", market="fx"))
    check("crypto pair", "price" in tools.borsa("quote", "BTCTRY", market="crypto"))
    history = tools.borsa("history", "GARAN", period="5d")
    check("history clipped to the context budget", len(history) <= config.MAX_TOOL_CHARS + 60,
          f"{len(history)} chars")
    check("technical indicators", "rsi" in tools.borsa("technical", "GARAN").lower())
    check("TEFAS fund", "TPC" in tools.borsa("fund", "TPC").upper())
    check("bad action explained", "Unknown action" in tools.borsa("moon", "THYAO"))
    # USD is also a US ETF ticker; a currency code must never return a share price.
    dollar = tools.borsa("quote", "USD", market="us")
    check("a currency code is never read as a share", "market: fx" in dollar, dollar)
    pair = tools.borsa("quote", "USDTRY")
    check("a currency pair is redirected, not guessed at",
          "convert_currency" in pair and "from_currency=USD" in pair, pair)

    section("portfolio valuation (ledger + live prices)")
    tools.portfolio_tool("add", symbol="THYAO", quantity=10, cost=280.0)
    valuation = tools.portfolio_tool("value")
    check("prices the position", "THYAO" in valuation and "TRY" in valuation, valuation)
    check("profit and loss shown", "P/L" in valuation)
    check("total per currency", "TOTAL TRY" in valuation)

    section("MCP session")
    from mcp_client import MCPClient
    client = MCPClient()
    remote = client.list_tools()
    check("handshake and tools/list", len(remote) > 10, f"{len(remote)} tools offered")
    check("a second call reuses the session", "current_price" in
          tools.borsa("quote", "ASELS", market="bist"))
    client.close()


if __name__ == "__main__":
    offline_checks()
    if "--offline" not in sys.argv:
        online_checks()
    print(f"\n\033[1m{results['pass']} passed, {results['fail']} failed\033[0m")
    sys.exit(1 if results["fail"] else 0)
