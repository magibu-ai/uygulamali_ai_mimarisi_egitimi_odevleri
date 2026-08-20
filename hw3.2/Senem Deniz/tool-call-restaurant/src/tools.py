"""
tools.py
--------
Modelin cagirabilecegi ARAC (tool) fonksiyonlari.
Her fonksiyon:
  * girdilerini dogrular,
  * veritabanindan GERCEK veri okur/yazar,
  * JSON-serilestirilebilir bir dict dondurur.

Onemli: Model bu fonksiyonlarin ciktisi disinda bilgi uretmemeli.
Bir urun/siparis bulunamazsa fonksiyon acikca {"error": ...} dondurur,
boylece halusinasyon yerine gercek durum modele iletilir.
"""

from typing import Optional
from .database import get_connection


# ---------------------------------------------------------------------------
# 1) Menu okuma (READ)
# ---------------------------------------------------------------------------
def get_menu(category: Optional[str] = None) -> dict:
    """Menuyu getirir. category verilirse (ana/tatli/icecek) filtreler."""
    query = "SELECT name, category, price, stock FROM menu"
    params: tuple = ()
    if category:
        query += " WHERE lower(category) = lower(?)"
        params = (category.strip(),)
    query += " ORDER BY category, name"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    if not rows:
        return {"error": f"'{category}' kategorisinde urun bulunamadi.",
                "available_categories": ["ana", "tatli", "icecek"]}

    items = [
        {"name": r["name"], "category": r["category"],
         "price": r["price"], "in_stock": r["stock"] > 0}
        for r in rows
    ]
    return {"count": len(items), "items": items}


# ---------------------------------------------------------------------------
# 2) Siparis olusturma (WRITE) — stok dususu ile
# ---------------------------------------------------------------------------
def create_order(customer: str, items: list, table_no: Optional[int] = None) -> dict:
    """
    Yeni siparis olusturur.
    items: [{"name": "Kunefe", "quantity": 2}, ...]
    - Urun menude yoksa veya stok yetersizse siparis OLUSTURULMAZ.
    - Basarili olursa stok dusulur, toplam tutar hesaplanir.
    """
    if not customer or not str(customer).strip():
        return {"error": "Musteri adi zorunludur."}
    if not items:
        return {"error": "Siparis en az bir urun icermelidir."}

    with get_connection() as conn:
        cur = conn.cursor()
        validated = []
        total = 0.0

        # Once tum urunleri dogrula (atomik davranis icin)
        for it in items:
            name = str(it.get("name", "")).strip()
            qty = int(it.get("quantity", 1))
            if qty <= 0:
                return {"error": f"Gecersiz adet: {name} ({qty})."}

            row = cur.execute(
                "SELECT id, price, stock FROM menu WHERE lower(name) = lower(?)",
                (name,),
            ).fetchone()

            if row is None:
                return {"error": f"'{name}' menude yok. Once get_menu ile kontrol edin."}
            if row["stock"] < qty:
                return {"error": f"'{name}' icin yeterli stok yok "
                                 f"(mevcut: {row['stock']}, istenen: {qty})."}

            validated.append((row["id"], name, qty, row["price"]))
            total += row["price"] * qty

        # Dogrulama gecti -> yaz
        cur.execute(
            "INSERT INTO orders (customer, table_no, status, total) VALUES (?, ?, 'hazirlaniyor', ?)",
            (customer.strip(), table_no, total),
        )
        order_id = cur.lastrowid

        for menu_id, _name, qty, _price in validated:
            cur.execute(
                "INSERT INTO order_items (order_id, menu_id, quantity) VALUES (?, ?, ?)",
                (order_id, menu_id, qty),
            )
            cur.execute("UPDATE menu SET stock = stock - ? WHERE id = ?", (qty, menu_id))

    return {
        "order_id": order_id,
        "customer": customer.strip(),
        "table_no": table_no,
        "status": "hazirlaniyor",
        "total": round(total, 2),
        "items": [{"name": n, "quantity": q} for _, n, q, _ in validated],
        "message": f"Siparis #{order_id} olusturuldu. Toplam: {round(total, 2)} TL.",
    }


# ---------------------------------------------------------------------------
# 3) Siparis durumu sorgulama (READ)
# ---------------------------------------------------------------------------
def check_order_status(order_id: int) -> dict:
    """Verilen siparis numarasinin durumunu ve icerigini dondurur."""
    try:
        order_id = int(order_id)
    except (TypeError, ValueError):
        return {"error": "order_id bir sayi olmalidir."}

    with get_connection() as conn:
        order = conn.execute(
            "SELECT id, customer, table_no, status, total, created_at "
            "FROM orders WHERE id = ?", (order_id,)
        ).fetchone()

        if order is None:
            return {"error": f"#{order_id} numarali siparis bulunamadi."}

        rows = conn.execute(
            "SELECT m.name AS name, oi.quantity AS quantity "
            "FROM order_items oi JOIN menu m ON m.id = oi.menu_id "
            "WHERE oi.order_id = ?", (order_id,)
        ).fetchall()

    return {
        "order_id": order["id"],
        "customer": order["customer"],
        "table_no": order["table_no"],
        "status": order["status"],
        "total": order["total"],
        "created_at": order["created_at"],
        "items": [{"name": r["name"], "quantity": r["quantity"]} for r in rows],
    }


# ---------------------------------------------------------------------------
# Fonksiyon yonlendirme haritasi (agent bu dict'ten cagirir)
# ---------------------------------------------------------------------------
TOOL_REGISTRY = {
    "get_menu": get_menu,
    "create_order": create_order,
    "check_order_status": check_order_status,
}
