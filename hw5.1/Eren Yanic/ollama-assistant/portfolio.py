"""The private half of the assistant: a local ledger of what you own.

Holdings live in a SQLite file on this machine and are never sent anywhere. Valuing the
portfolio does reach the network, but only to ask "what is SYMBOL worth" — the quantity
you hold and the price you paid stay here. That is why pricing is injected as a callable
rather than imported: this module owns storage and arithmetic, nothing else.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import datetime

import config

MARKETS = ("bist", "us", "crypto", "fx", "fund")

SCHEMA = """
CREATE TABLE IF NOT EXISTS holdings (
    symbol      TEXT PRIMARY KEY,
    market      TEXT NOT NULL,
    quantity    REAL NOT NULL,
    cost        REAL,           -- average unit cost paid, in the asset's own currency
    updated_at  TEXT NOT NULL
);
"""

# A quote lookup: (symbol, market) -> (price, currency). Returns None when unavailable.
PriceLookup = Callable[[str, str], "tuple[float, str] | None"]


def _connect() -> sqlite3.Connection:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(config.DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute(SCHEMA)
    return connection


def _money(value: float) -> str:
    return f"{value:,.2f}"


def add(symbol: str, market: str, quantity: float, cost: float | None = None) -> str:
    """Add to a position, keeping a weighted-average cost when one already exists."""
    symbol = symbol.strip().upper()
    market = market.strip().lower()
    if market not in MARKETS:
        return f"Unknown market '{market}'. Use one of: {', '.join(MARKETS)}."
    if quantity <= 0:
        return "Quantity must be greater than zero."

    with closing(_connect()) as connection, connection:
        row = connection.execute(
            "SELECT quantity, cost FROM holdings WHERE symbol = ?", (symbol,)
        ).fetchone()

        if row is None:
            new_quantity, new_cost = quantity, cost
        else:
            new_quantity = row["quantity"] + quantity
            if cost is not None and row["cost"] is not None:
                # Weighted average of what was already held and what was just bought.
                new_cost = (row["quantity"] * row["cost"] + quantity * cost) / new_quantity
            else:
                new_cost = cost if row["cost"] is None else row["cost"]

        connection.execute(
            "INSERT INTO holdings (symbol, market, quantity, cost, updated_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(symbol) DO UPDATE SET "
            "market = excluded.market, quantity = excluded.quantity, "
            "cost = excluded.cost, updated_at = excluded.updated_at",
            (symbol, market, new_quantity, new_cost, datetime.now().isoformat(timespec="seconds")),
        )

    held = f"{new_quantity:g} {symbol}"
    if new_cost:
        return f"Added. You now hold {held} ({market}), average cost {_money(new_cost)} per unit."
    return f"Added. You now hold {held} ({market})."


def remove(symbol: str, quantity: float | None = None) -> str:
    """Sell part of a position, or drop it entirely when quantity is omitted."""
    symbol = symbol.strip().upper()
    with closing(_connect()) as connection, connection:
        row = connection.execute(
            "SELECT quantity FROM holdings WHERE symbol = ?", (symbol,)
        ).fetchone()
        if row is None:
            return f"{symbol} is not in the portfolio."

        if quantity is None or quantity >= row["quantity"]:
            connection.execute("DELETE FROM holdings WHERE symbol = ?", (symbol,))
            return f"Removed {symbol} from the portfolio."

        remaining = row["quantity"] - quantity
        connection.execute(
            "UPDATE holdings SET quantity = ?, updated_at = ? WHERE symbol = ?",
            (remaining, datetime.now().isoformat(timespec="seconds"), symbol),
        )
        return f"Sold {quantity:g} {symbol}. {remaining:g} left."


def holdings() -> list[dict]:
    with closing(_connect()) as connection:
        return [dict(row) for row in connection.execute(
            "SELECT symbol, market, quantity, cost FROM holdings ORDER BY symbol"
        )]


def listing() -> str:
    rows = holdings()
    if not rows:
        return "The portfolio is empty. Add something with the portfolio tool, action='add'."
    lines = [f"{len(rows)} position(s):"]
    for row in rows:
        cost = f", average cost {_money(row['cost'])}" if row["cost"] else ""
        lines.append(f"- {row['symbol']} ({row['market']}): {row['quantity']:g} units{cost}")
    return "\n".join(lines)


def valuation(price_lookup: PriceLookup) -> str:
    """Price every position and total it up, grouped by the currency each trades in."""
    rows = holdings()
    if not rows:
        return "The portfolio is empty, so there is nothing to value."

    lines, totals, unpriced = [], {}, []
    for row in rows:
        quote = price_lookup(row["symbol"], row["market"])
        if quote is None:
            unpriced.append(row["symbol"])
            lines.append(f"- {row['symbol']}: {row['quantity']:g} units, no live price available")
            continue

        price, currency = quote
        value = price * row["quantity"]
        totals[currency] = totals.get(currency, 0.0) + value

        line = (f"- {row['symbol']}: {row['quantity']:g} x {_money(price)} "
                f"= {_money(value)} {currency}")
        if row["cost"]:
            invested = row["cost"] * row["quantity"]
            change = value - invested
            percent = (change / invested * 100) if invested else 0.0
            line += f" | cost {_money(invested)}, P/L {change:+,.2f} ({percent:+.1f}%)"
        lines.append(line)

    for currency, total in sorted(totals.items()):
        lines.append(f"TOTAL {currency}: {_money(total)}")
    if unpriced:
        lines.append(f"Note: no price for {', '.join(unpriced)}; excluded from the total.")
    # Totals are per currency on purpose: converting them into one currency is the
    # model's job, using convert_currency, so the rate it used stays visible.
    return "\n".join(lines)
