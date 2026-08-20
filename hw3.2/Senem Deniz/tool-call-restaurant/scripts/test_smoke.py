"""
test_smoke.py — hizli dogrulama testleri.
Calistir:  python -m scripts.test_smoke
"""
import json
from src.database import init_db
from src.tools import get_menu, create_order, check_order_status


def run():
    init_db(force=True)
    ok = 0

    # 1) Menu okuma
    menu = get_menu("tatli")
    assert menu["count"] == 3, menu
    ok += 1

    # 2) Gecerli siparis + stok dususu
    before = next(i for i in get_menu()["items"] if i["name"] == "Kunefe")
    order = create_order("Ali", [{"name": "Kunefe", "quantity": 2}], table_no=5)
    assert order["order_id"] == 1 and order["total"] == 240.0, order
    ok += 1

    # 3) Siparis durumu
    st = check_order_status(1)
    assert st["status"] == "hazirlaniyor" and st["table_no"] == 5, st
    ok += 1

    # 4) Halusinasyon engelleme: menude olmayan urun reddedilir
    bad = create_order("Veli", [{"name": "Uzay Burgeri", "quantity": 1}])
    assert "error" in bad, bad
    ok += 1

    # 5) Stok yetersizligi reddedilir
    toomuch = create_order("Ayse", [{"name": "Baklava", "quantity": 999}])
    assert "error" in toomuch, toomuch
    ok += 1

    # 6) Olmayan siparis numarasi
    missing = check_order_status(9999)
    assert "error" in missing, missing
    ok += 1

    print(f"✅ {ok}/6 test gecti.")


if __name__ == "__main__":
    run()
