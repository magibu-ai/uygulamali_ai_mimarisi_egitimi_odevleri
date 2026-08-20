import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).parent / "banka.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name   TEXT NOT NULL,
    phone       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS accounts (
    account_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(user_id),
    account_number  TEXT NOT NULL UNIQUE,
    account_type    TEXT NOT NULL CHECK (account_type IN ('vadesiz', 'vadeli', 'tasarruf')),
    currency        TEXT NOT NULL DEFAULT 'TRY',
    balance         REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cards (
    card_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id    INTEGER NOT NULL REFERENCES accounts(account_id),
    card_number   TEXT NOT NULL,
    card_type     TEXT NOT NULL CHECK (card_type IN ('debit', 'credit', 'virtual')),
    status        TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'blocked'))
);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id           INTEGER NOT NULL REFERENCES accounts(account_id),
    type                  TEXT NOT NULL CHECK (type IN ('transfer_in', 'transfer_out', 'deposit', 'withdrawal')),
    amount                REAL NOT NULL,
    description           TEXT,
    related_account_id    INTEGER REFERENCES accounts(account_id),
    created_at            TEXT NOT NULL
);
"""


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_schema():
    conn = get_connection()
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ============================================================
# YAZMA — kayıt oluşturma (seed_data.py'nin de kullandığı temel fonksiyonlar)
# ============================================================

def create_user(conn, full_name: str, phone: str) -> int:
    cursor = conn.execute(
        "INSERT INTO users (full_name, phone) VALUES (?, ?)",
        (full_name, phone),
    )
    return cursor.lastrowid


def create_account(conn, user_id: int, account_number: str, account_type: str, currency: str = "TRY", balance: float = 0.0) -> int:
    cursor = conn.execute(
        "INSERT INTO accounts (user_id, account_number, account_type, currency, balance) VALUES (?, ?, ?, ?, ?)",
        (user_id, account_number, account_type, currency, balance),
    )
    return cursor.lastrowid


def record_transaction(conn, account_id: int, type_: str, amount: float, description: str, related_account_id: int | None = None) -> int:
    cursor = conn.execute(
        "INSERT INTO transactions (account_id, type, amount, description, related_account_id, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (account_id, type_, amount, description, related_account_id, _now()),
    )
    return cursor.lastrowid


# ============================================================
# OKUMA — tool'ların doğrudan kullanacağı fonksiyonlar
# ============================================================

def find_users_by_name(conn, name: str) -> list[dict]:
    pattern = f"%{name}%"
    rows = conn.execute(
        "SELECT user_id, full_name, phone FROM users WHERE full_name LIKE ? COLLATE NOCASE",
        (pattern,),
    ).fetchall()
    return [dict(row) for row in rows]


def list_accounts(conn, user_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT account_id, account_number, account_type, currency, balance FROM accounts WHERE user_id = ? ORDER BY account_id",
        (user_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_account(conn, account_id: int) -> dict | None:
    row = conn.execute(
        "SELECT account_id, user_id, account_number, account_type, currency, balance FROM accounts WHERE account_id = ?",
        (account_id,),
    ).fetchone()
    return dict(row) if row else None


def get_balance(conn, account_id: int) -> dict | None:
    row = conn.execute(
        "SELECT account_id, account_number, currency, balance FROM accounts WHERE account_id = ?",
        (account_id,),
    ).fetchone()
    return dict(row) if row else None


def get_transaction_history(conn, account_id: int, limit: int = 10) -> list[dict]:
    rows = conn.execute(
        "SELECT transaction_id, type, amount, description, related_account_id, created_at "
        "FROM transactions WHERE account_id = ? ORDER BY transaction_id DESC LIMIT ?",
        (account_id, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def get_card(conn, card_id: int) -> dict | None:
    row = conn.execute(
        "SELECT card_id, account_id, card_number, card_type, status FROM cards WHERE card_id = ?",
        (card_id,),
    ).fetchone()
    return dict(row) if row else None


# ============================================================
# DÖVİZ KURLARI — sabit, kur senaryosu için (gerçek zamanlı değil)
# ============================================================

EXCHANGE_RATES_TO_TRY = {
    "TRY": 1.0,
    "EUR": 35.0,
    "USD": 32.0,
}


def convert_amount(amount: float, from_currency: str, to_currency: str) -> float:
    if from_currency not in EXCHANGE_RATES_TO_TRY:
        raise ValueError(f"Bilinmeyen para birimi: {from_currency}")
    if to_currency not in EXCHANGE_RATES_TO_TRY:
        raise ValueError(f"Bilinmeyen para birimi: {to_currency}")

    amount_in_try = amount * EXCHANGE_RATES_TO_TRY[from_currency]
    return round(amount_in_try / EXCHANGE_RATES_TO_TRY[to_currency], 2)


# ============================================================
# YAZMA — iş kuralı içeren, tool'ların çağıracağı fonksiyonlar
# ============================================================

def transfer_money(conn, from_account_id: int, to_account_id: int, amount: float, description: str = "") -> dict:
    """Aynı para birimindeki iki hesap arasında transfer yapar."""
    if amount <= 0:
        raise ValueError("Transfer tutarı pozitif olmalıdır.")
    if from_account_id == to_account_id:
        raise ValueError("Gönderen ve alıcı hesap aynı olamaz.")

    from_account = get_account(conn, from_account_id)
    if from_account is None:
        raise ValueError(f"Gönderen hesap bulunamadı: {from_account_id}")

    to_account = get_account(conn, to_account_id)
    if to_account is None:
        raise ValueError(f"Alıcı hesap bulunamadı: {to_account_id}")

    if from_account["currency"] != to_account["currency"]:
        raise ValueError(
            f"Para birimi uyuşmuyor: {from_account['currency']} -> {to_account['currency']}. "
            "Farklı para birimleri arasında transfer için exchange_transfer kullanılmalı."
        )

    if from_account["balance"] < amount:
        raise ValueError(
            f"Yetersiz bakiye. Mevcut bakiye: {from_account['balance']} {from_account['currency']}, istenen: {amount}"
        )

    conn.execute("UPDATE accounts SET balance = balance - ? WHERE account_id = ?", (amount, from_account_id))
    conn.execute("UPDATE accounts SET balance = balance + ? WHERE account_id = ?", (amount, to_account_id))

    record_transaction(conn, from_account_id, "transfer_out", amount, description or f"{to_account['account_number']} hesabına transfer", to_account_id)
    record_transaction(conn, to_account_id, "transfer_in", amount, description or f"{from_account['account_number']} hesabından transfer", from_account_id)

    return {
        "from_account_id": from_account_id,
        "to_account_id": to_account_id,
        "amount": amount,
        "currency": from_account["currency"],
        "from_account_new_balance": from_account["balance"] - amount,
        "to_account_new_balance": to_account["balance"] + amount,
    }


def exchange_transfer(conn, from_account_id: int, to_account_id: int, amount: float, description: str = "") -> dict:
    """Farklı para birimindeki iki hesap arasında, sabit demo kuruyla transfer yapar."""
    if amount <= 0:
        raise ValueError("Transfer tutarı pozitif olmalıdır.")
    if from_account_id == to_account_id:
        raise ValueError("Gönderen ve alıcı hesap aynı olamaz.")

    from_account = get_account(conn, from_account_id)
    if from_account is None:
        raise ValueError(f"Gönderen hesap bulunamadı: {from_account_id}")

    to_account = get_account(conn, to_account_id)
    if to_account is None:
        raise ValueError(f"Alıcı hesap bulunamadı: {to_account_id}")

    if from_account["currency"] == to_account["currency"]:
        raise ValueError(
            "İki hesap da aynı para biriminde — bu işlem için transfer_money kullanılmalı, exchange_transfer değil."
        )

    if from_account["balance"] < amount:
        raise ValueError(
            f"Yetersiz bakiye. Mevcut bakiye: {from_account['balance']} {from_account['currency']}, istenen: {amount}"
        )

    converted_amount = convert_amount(amount, from_account["currency"], to_account["currency"])

    conn.execute("UPDATE accounts SET balance = balance - ? WHERE account_id = ?", (amount, from_account_id))
    conn.execute("UPDATE accounts SET balance = balance + ? WHERE account_id = ?", (converted_amount, to_account_id))

    note = f"Döviz transferi ({from_account['currency']} -> {to_account['currency']})"
    record_transaction(conn, from_account_id, "transfer_out", amount, description or f"{to_account['account_number']} hesabına {note}", to_account_id)
    record_transaction(conn, to_account_id, "transfer_in", converted_amount, description or f"{from_account['account_number']} hesabından {note}", from_account_id)

    return {
        "from_account_id": from_account_id,
        "to_account_id": to_account_id,
        "sent_amount": amount,
        "sent_currency": from_account["currency"],
        "received_amount": converted_amount,
        "received_currency": to_account["currency"],
        "exchange_rate_note": "Sabit demo kuru kullanılmıştır, gerçek zamanlı piyasa kuru değildir.",
        "from_account_new_balance": from_account["balance"] - amount,
        "to_account_new_balance": to_account["balance"] + converted_amount,
    }


def create_card(conn, account_id: int, card_type: str) -> dict:
    if card_type not in {"debit", "credit", "virtual"}:
        raise ValueError(f"Geçersiz kart tipi: {card_type}")

    account = get_account(conn, account_id)
    if account is None:
        raise ValueError(f"Hesap bulunamadı: {account_id}")

    existing_count = conn.execute("SELECT COUNT(*) AS c FROM cards WHERE account_id = ?", (account_id,)).fetchone()["c"]
    card_number = f"{4000 + existing_count:04d} **** **** {1000 + account_id:04d}"

    cursor = conn.execute(
        "INSERT INTO cards (account_id, card_number, card_type, status) VALUES (?, ?, ?, 'active')",
        (account_id, card_number, card_type),
    )

    return {"card_id": cursor.lastrowid, "account_id": account_id, "card_number": card_number, "card_type": card_type, "status": "active"}


def block_card(conn, card_id: int) -> dict:
    card = get_card(conn, card_id)
    if card is None:
        raise ValueError(f"Kart bulunamadı: {card_id}")
    if card["status"] == "blocked":
        return {"card_id": card_id, "status": "blocked", "already_blocked": True}
    conn.execute("UPDATE cards SET status = 'blocked' WHERE card_id = ?", (card_id,))
    return {"card_id": card_id, "status": "blocked", "already_blocked": False}
def open_new_account(conn, user_id: int, account_type: str, currency: str = "TRY") -> dict:
    if account_type not in {"vadesiz", "vadeli", "tasarruf"}:
        raise ValueError(f"Geçersiz hesap tipi: {account_type}")
    if currency not in EXCHANGE_RATES_TO_TRY:
        raise ValueError(f"Bilinmeyen para birimi: {currency}")

    user_row = conn.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if user_row is None:
        raise ValueError(f"Kullanıcı bulunamadı: {user_id}")

    next_id = conn.execute(
        "SELECT COALESCE(MAX(account_id), 0) + 1 AS next_id FROM accounts"
    ).fetchone()["next_id"]
    account_number = f"TR{10 + next_id:02d} 0006 1000 0000 {1000 + next_id:04d} {next_id:04d} 01"

    account_id = create_account(conn, user_id, account_number, account_type, currency, balance=0.0)

    return {
        "account_id": account_id,
        "user_id": user_id,
        "account_number": account_number,
        "account_type": account_type,
        "currency": currency,
        "balance": 0.0,
    }

if __name__ == "__main__":
    init_schema()
    print(f"Veritabanı oluşturuldu: {DB_PATH}")