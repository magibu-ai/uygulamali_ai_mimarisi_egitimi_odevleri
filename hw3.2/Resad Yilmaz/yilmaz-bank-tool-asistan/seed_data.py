import random
from datetime import datetime, timezone

import database as db

random.seed(42)  # her çalıştırmada aynı "rastgele" veriyi üretir

FIRST_NAMES = [
    "Ayşe", "Mehmet", "Zeynep", "Can", "Elif", "Emre", "Selin", "Burak",
    "Deniz", "Gizem", "Hakan", "İrem", "Kerem", "Merve", "Onur", "Pınar",
    "Serkan", "Tuğçe", "Volkan", "Yasemin", "Ahmet", "Buse", "Cem", "Derya",
]

LAST_NAMES = [
    "Demir", "Yıldız", "Kaya", "Öztürk", "Çelik", "Şahin", "Aydın", "Arslan",
    "Doğan", "Kılıç", "Aslan", "Çetin", "Koç", "Kurt", "Özkan", "Şimşek",
]

ACCOUNT_TYPES = ["vadesiz", "vadeli", "tasarruf"]
CURRENCIES = ["TRY", "TRY", "TRY", "TRY", "USD", "EUR"]  # TRY ağırlıklı olsun


def random_phone():
    return f"05{random.randint(30, 55)} {random.randint(100,999)} {random.randint(10,99)} {random.randint(10,99)}"


def random_account_number(index):
    # Gerçekçi görünen ama tamamen uydurma bir IBAN benzeri numara
    return f"TR{10 + index:02d} 0006 1000 0000 {1000+index:04d} {index:04d} 01"


def main():
    db.init_schema()
    conn = db.get_connection()

    account_counter = 0

    for first_name in FIRST_NAMES:
        for last_name in random.sample(LAST_NAMES, k=1):  # her isme 1 soyisim eşleştir
            full_name = f"{first_name} {last_name}"
            phone = random_phone()

            cursor = conn.execute(
                "INSERT INTO users (full_name, phone) VALUES (?, ?)",
                (full_name, phone),
            )
            user_id = cursor.lastrowid

            # Her kullanıcıya 2 ile 3 arası hesap
            num_accounts = random.randint(2, 3)

            for _ in range(num_accounts):
                account_counter += 1
                account_type = random.choice(ACCOUNT_TYPES)
                currency = random.choice(CURRENCIES)
                balance = round(random.uniform(500, 75000), 2)
                account_number = random_account_number(account_counter)

                acc_cursor = conn.execute(
                    "INSERT INTO accounts (user_id, account_number, account_type, currency, balance) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (user_id, account_number, account_type, currency, balance),
                )
                account_id = acc_cursor.lastrowid

                # Açılış bakiyesini bir "deposit" işlemi olarak da kaydedelim
                conn.execute(
                    "INSERT INTO transactions (account_id, type, amount, description, related_account_id, created_at) "
                    "VALUES (?, 'deposit', ?, 'Hesap açılış bakiyesi', NULL, ?)",
                    (account_id, balance, datetime.now(timezone.utc).isoformat(timespec="seconds")),
                )

                # %60 ihtimalle bir kart da ekleyelim
                if random.random() < 0.6:
                    card_type = random.choice(["debit", "credit", "virtual"])
                    card_number = f"{random.randint(4000,4999)} **** **** {1000+account_id:04d}"
                    conn.execute(
                        "INSERT INTO cards (account_id, card_number, card_type, status) VALUES (?, ?, ?, 'active')",
                        (account_id, card_number, card_type),
                    )

    conn.commit()

    total_users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    total_accounts = conn.execute("SELECT COUNT(*) AS c FROM accounts").fetchone()["c"]
    total_cards = conn.execute("SELECT COUNT(*) AS c FROM cards").fetchone()["c"]
    conn.close()

    print(f"{total_users} kullanıcı, {total_accounts} hesap, {total_cards} kart oluşturuldu.")


if __name__ == "__main__":
    main()