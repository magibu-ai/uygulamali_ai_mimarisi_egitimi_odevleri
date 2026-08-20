import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "hydrology.db"


def init_db():
    DATA_DIR.mkdir(exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    # 1. İstasyon tablosu
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS stations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            river TEXT NOT NULL,
            province TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1
                CHECK (active IN (0, 1))
        )
        """
    )

    # 2. Ölçüm tablosu
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            station_id INTEGER NOT NULL,
            measured_at TEXT NOT NULL,
            flow_m3s REAL NOT NULL CHECK (flow_m3s >= 0),
            water_level_m REAL NOT NULL CHECK (water_level_m >= 0),
            FOREIGN KEY (station_id)
                REFERENCES stations(id)
                ON DELETE CASCADE,
            UNIQUE(station_id, measured_at)
        )
        """
    )

    # 3. Uyarı tablosu
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            station_id INTEGER NOT NULL,
            threshold_m3s REAL NOT NULL
                CHECK (threshold_m3s > 0),
            note TEXT,
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            created_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (station_id)
                REFERENCES stations(id)
                ON DELETE CASCADE
        )
        """
    )

    # Örnek / sentetik istasyonlar
    stations = [
        (
            "Kirazdere",
            "Kirazdere Deresi",
            "Kocaeli",
            1,
        ),
        (
            "Yuvacık",
            "Yuvacık Barajı Girişi",
            "Kocaeli",
            1,
        ),
        (
            "Kullar",
            "Kullar Deresi",
            "Kocaeli",
            1,
        ),
    ]

    cursor.executemany(
        """
        INSERT OR IGNORE INTO stations (
            name,
            river,
            province,
            active
        )
        VALUES (?, ?, ?, ?)
        """,
        stations,
    )

    # Kirazdere ID
    cursor.execute(
        """
        SELECT id
        FROM stations
        WHERE name = ?
        """,
        ("Kirazdere",),
    )

    kirazdere_id = cursor.fetchone()[0]

    # Sentetik ölçümler
    measurements = [
        (
            kirazdere_id,
            "2026-08-01 01:30",
            58.4,
            2.17,
        ),
        (
            kirazdere_id,
            "2026-08-01 02:00",
            61.2,
            2.25,
        ),
    ]

    cursor.executemany(
        """
        INSERT OR IGNORE INTO measurements (
            station_id,
            measured_at,
            flow_m3s,
            water_level_m
        )
        VALUES (?, ?, ?, ?)
        """,
        measurements,
    )

    conn.commit()
    conn.close()

    print("Veritabanı hazır.")
    print(f"Dosya: {DB_PATH}")


if __name__ == "__main__":
    init_db()