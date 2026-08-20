#!/usr/bin/env bash
# Postgres/pgvector/ParadeDB'yi docker ile ayağa kaldırıp Wikipedia dump'ını yükler.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo ".env bulunamadı. Önce: cp .env.example .env  (ve HF_DATASET_REPO'yu doldurun)" >&2
  exit 1
fi
set -a; source .env; set +a

echo "== 1/2: Postgres container'ı ayağa kalkıyor =="
docker compose up -d

echo "== bekleniyor: veritabanı hazır olsun =="
until docker compose exec -T wiki-db pg_isready -U "${POSTGRES_USER:-kg}" >/dev/null 2>&1; do
  sleep 1
done

echo "== 2/2: dump Postgres'e yükleniyor =="
python3 load_dump.py "$@"

echo "Tamamlandı."
