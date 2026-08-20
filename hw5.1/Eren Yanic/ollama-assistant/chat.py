"""Terminal assistant: a local model, eight tools, and a loop between them.

    you ask -> the model answers, or calls a tool
            -> we run the tool and hand back the result
            -> repeat until it has what it needs, then it writes the answer

Usage:
    python chat.py                     # interactive
    python chat.py --ask "..."         # one question, then exit
    python chat.py --model qwen3:1.7b  # a smaller model
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from datetime import datetime
from pathlib import Path

import config
import ollama_client
import tools

# ANSI colours. Cheaper than a dependency, and the trace is worth having in colour.
DIM, BOLD, CYAN, GREEN, YELLOW, RED, RESET = (
    "\033[2m", "\033[1m", "\033[36m", "\033[32m", "\033[33m", "\033[31m", "\033[0m"
)

SYSTEM_PROMPT = """You are a personal assistant running locally on the user's own computer.
Today is {today} and the user's time zone is {timezone}.

Reply in the same language the user writes in.

WHICH TOOL:
- borsa: prices and analysis for shares, indices, funds, gold, silver, oil
  (THYAO, AAPL, XU100, gram-altin). Also company news from KAP.
- convert_currency: exchange rates and money conversion, crypto included - "1 dolar kac
  TL", "what is the euro rate", "how many dollars is Bitcoin", "0.5 ETH in euros".
  A currency pair like USDTRY is never a borsa symbol; it belongs here.
- portfolio: anything the user owns - "my shares", "my portfolio", "what am I worth".
- get_weather: weather. get_datetime: the date, or the time in another city.
- calculate: arithmetic. run_python: loops, algorithms, date differences, lists.
- web_search: news, current events, and any fact the tools above cannot supply.

RULES:
1. You cannot know today's prices, rates, weather or news, and your memory of events
   ends before today. Get those from a tool, every time. Never guess one.
2. Do no arithmetic in your head - not multiplication, not percentages, not VAT, not
   totals. "1250 x 1.18" and "18% of 18500" both go to calculate. Anything needing a
   loop or a list - primes, sorting, days between dates - goes to run_python.
   Turning a price into another currency is a convert_currency call on the number the
   first tool returned. Multiplying by a rate yourself is always wrong.
3. Asked about news, "today", "the latest" anything? Call web_search. Saying you cannot
   know is wrong: searching is exactly what you are for.
4. One tool call at a time - but keep going until the whole question is answered. If it
   has two parts, such as the weather AND the time, call the second tool after reading
   the first result. Never tell the user to ask again for the other half.
5. Use only numbers that came from a tool result or from the user. If a tool fails, say
   so plainly - never invent the value it would have returned.
6. Never put a number in a tool argument that the user did not give you. If they say
   "add 0.05 BTC" with no price, send no cost at all. A guessed purchase price turns
   into a fake profit, which is worse than no answer.
7. Answer in one to three sentences unless more is asked for. Always give the currency,
   and for market data say when the figure was measured.
8. Greetings and small talk need no tool.
9. You report data; you do not give investment advice.
10. Tool results come back in English. Your answer must still be in the user's language -
    translate the numbers into their sentence, do not copy the tool's wording.

Worked example. "18500 liranin yuzde 18 KDV'si ne kadar?" is a calculation, so you call
calculate with expression "18500 * 0.18" and report what it returns. Doing that sum
yourself, however easy it looks, is a mistake: every question that combines numbers -
a percentage, a total, a division, a share of a bill - is a calculate call."""

BANNER_COMMANDS = "/tools  /reset  /log  exit"

# One worked exchange, replayed at the head of every conversation.
#
# The written rule above was not enough on its own: asked in English the model called
# calculate, asked the same thing in Turkish it did the sum in its head, because its
# grip on an English system prompt loosens once it switches language. A demonstrated
# tool call in Turkish fixed that where three rewordings of the rule had not. It costs
# about a hundred tokens of the context window, which is the cheapest reliability we buy
# anywhere in this project.
PRIMER = [
    {"role": "user", "content": "780 liranın yüzde 12'si ne kadar?"},
    {"role": "assistant", "content": "", "tool_calls": [
        {"function": {"name": "calculate", "arguments": {"expression": "780 * 0.12"}}}]},
    {"role": "tool", "tool_name": "calculate", "content": "780 * 0.12 = 93.6"},
    {"role": "assistant", "content": "780 liranın %12'si 93,60 TL eder."},
]


def build_system_prompt() -> str:
    now = datetime.now().astimezone()
    return SYSTEM_PROMPT.format(today=f"{now:%A, %d %B %Y}", timezone=f"{now:%Z} (UTC{now:%z})")


class SessionLog:
    """One JSONL file per session: every turn and every tool call, secrets redacted."""

    def __init__(self) -> None:
        config.LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.path: Path = config.LOG_DIR / f"session-{datetime.now():%Y%m%d-%H%M%S}.jsonl"

    def write(self, kind: str, **fields) -> None:
        record = {"time": datetime.now().isoformat(timespec="seconds"), "event": kind, **fields}
        line = config.redact(json.dumps(record, ensure_ascii=False, default=str))
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


# Anything typed at the confirmation prompt that was not an answer to it: the user was
# asking the next question, so it waits here rather than being swallowed as a "no".
_pushback: list[str] = []


def read_input(prompt: str) -> str:
    """input(), but echoing when stdin is piped so a scripted run reads like a session."""
    if _pushback:
        return _pushback.pop()
    text = input(prompt)
    if not sys.stdin.isatty():
        print(text)
    return text


def ask_to_run(code: str) -> bool:
    """Show the model's code and ask before executing it."""
    print(f"\n{YELLOW}The assistant wants to run this Python:{RESET}")
    print(DIM + "\n".join(f"  │ {line}" for line in code.splitlines()) + RESET)
    try:
        answer = read_input(f"{YELLOW}Run it? [y/N] {RESET}").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if answer.lower() in {"y", "yes", "e", "evet"}:
        return True
    if answer and answer.lower() not in {"n", "no", "h", "hayir", "hayır"}:
        _pushback.append(answer)  # a new question, not a refusal — keep it for the loop
    return False


def format_arguments(arguments: dict) -> str:
    parts = []
    for key, value in arguments.items():
        text = str(value).replace("\n", " ")
        parts.append(f"{key}={text[:60] + '…' if len(text) > 60 else text}")
    return ", ".join(parts)


def handle_tool_calls(tool_calls: list[dict], log: SessionLog) -> list[dict]:
    """Run what the model asked for and turn each result into a tool message."""
    messages = []
    for call in tool_calls:
        name = call["function"]["name"]
        arguments = call["function"].get("arguments") or {}
        print(f"  {CYAN}🔧 {name}({format_arguments(arguments)}){RESET}", flush=True)
        log.write("tool_call", tool=name, arguments=arguments)

        result = tools.run(name, arguments)

        preview = " ".join(result.split())[:110]
        print(f"  {DIM}↳ {preview}{'…' if len(result) > 110 else ''}{RESET}", flush=True)
        log.write("tool_result", tool=name, chars=len(result), result=result)
        messages.append({"role": "tool", "tool_name": name, "content": result})
    return messages


def answer(messages: list[dict], model: str, log: SessionLog) -> str:
    """Drive the model until it stops calling tools, then return its final text."""
    for round_number in range(config.MAX_TOOL_ROUNDS):
        message = ollama_client.chat(messages, tools=tools.TOOL_SCHEMAS, model=model)
        messages.append(message)
        tool_calls = message.get("tool_calls")
        if not tool_calls:
            return (message.get("content") or "").strip()
        messages.extend(handle_tool_calls(tool_calls, log))

    # Out of rounds: ask for a final answer from what has been gathered.
    messages.append({"role": "user", "content":
                     "Answer now, using only the tool results above."})
    return (ollama_client.chat(messages, model=model).get("content") or "").strip()


def check_model(model: str) -> None:
    """Fail early and helpfully rather than midway through the first question."""
    try:
        installed = ollama_client.installed_models()
    except RuntimeError as exc:
        sys.exit(f"{RED}{exc}{RESET}")
    if model not in installed and f"{model}:latest" not in installed:
        print(f"{YELLOW}'{model}' is not installed. Pull it with:  ollama pull {model}{RESET}")
        if installed:
            print(f"{DIM}Installed: {', '.join(installed)}{RESET}")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Local assistant with tool calling.")
    parser.add_argument("--model", default=config.CHAT_MODEL, help="Ollama model to use")
    parser.add_argument("--ask", help="Ask one question, print the answer, and exit")
    arguments = parser.parse_args()

    check_model(arguments.model)
    tools.confirm_python = ask_to_run
    if config.MCP_WARMUP:
        # The market server sleeps when idle; wake it while the user is still typing.
        threading.Thread(target=tools.warm_market_data, daemon=True).start()
    log = SessionLog()
    messages = [{"role": "system", "content": build_system_prompt()}, *PRIMER]

    def respond(question: str) -> None:
        messages.append({"role": "user", "content": question})
        log.write("user", text=question)
        try:
            reply = answer(messages, arguments.model, log)
        except RuntimeError as exc:
            print(f"{RED}Error: {exc}{RESET}\n")
            log.write("error", text=str(exc))
            return
        print(f"\n{GREEN}{BOLD}assistant{RESET} {reply}\n")
        log.write("assistant", text=reply)

    if arguments.ask:
        respond(arguments.ask)
        return

    print(f"{BOLD}Local assistant{RESET} {DIM}·{RESET} {arguments.model} "
          f"{DIM}·{RESET} {len(tools.TOOL_SCHEMAS)} tools "
          f"{DIM}·{RESET} {config.NUM_CTX} token context")
    print(f"{DIM}log: {log.path.name}   commands: {BANNER_COMMANDS}{RESET}\n")

    while True:
        try:
            question = read_input(f"{BOLD}you{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not question:
            continue
        if question.lower() in {"exit", "quit", "cik", "çık", "/exit", "/quit"}:
            break
        if question == "/tools":
            for schema in tools.TOOL_SCHEMAS:
                function = schema["function"]
                print(f"  {CYAN}{function['name']:<17}{RESET}{function['description'][:90]}")
            print()
            continue
        if question == "/reset":
            del messages[1 + len(PRIMER):]  # keep the system prompt and the primer
            print(f"{DIM}Conversation cleared.{RESET}\n")
            continue
        if question == "/log":
            print(f"{DIM}{log.path}{RESET}\n")
            continue
        respond(question)


if __name__ == "__main__":
    main()
