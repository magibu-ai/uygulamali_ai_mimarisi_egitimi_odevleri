
"""
Eczane Sipariş Asistanı — Tool Fonksiyonları
get_drug_info, search_by_symptom, create_order, check_order_status
"""

import json
from db import find_drug, insert_drug, create_order_record, find_order, search_drugs_by_keyword
from search_provider import search_drug_info


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_drug_info",
            "description": "Belirli bir ilacın (örn. Parol, Majezik) stok durumunu ve prospektüs özetini getirir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "drug_name": {"type": "string", "description": "İlacın adı (örn. Parol, Majezik, Betaserc)"}
                },
                "required": ["drug_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_by_symptom",
            "description": "Kullanıcının şikayet/semptomuna (ör. baş dönmesi, ateş, mide bulantısı, baş ağrısı) uygun ilaçları veritabanında veya web'de arar ve önerir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symptom": {"type": "string", "description": "Semptom veya şikayet adı (örn. baş dönmesi, ateş, mide yanması)"}
                },
                "required": ["symptom"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_order",
            "description": "Belirtilen ilaçtan belirtilen adette sipariş oluşturur.",
            "parameters": {
                "type": "object",
                "properties": {
                    "drug_name": {"type": "string"},
                    "quantity": {"type": "integer"},
                },
                "required": ["drug_name", "quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_order_status",
            "description": "Sipariş numarasına göre sipariş durumunu sorgular.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer"}
                },
                "required": ["order_id"],
            },
        },
    },
]


def get_drug_info(drug_name: str) -> dict:
    drug = find_drug(drug_name)

    if drug:
        return {
            "drug_name": drug["display_name"],
            "stock": drug["stock"],
            "price": drug["price"],
            "prospektus_summary": drug["prospektus_summary"],
            "source": "db",
        }

    keyword_matches = search_drugs_by_keyword(drug_name)
    if keyword_matches:
        results = [
            {
                "drug_name": d["display_name"],
                "stock": d["stock"],
                "price": d["price"],
                "prospektus_summary": d["prospektus_summary"],
            }
            for d in keyword_matches
        ]
        return {
            "search_query": drug_name,
            "matching_drugs": results,
            "source": "db_keyword_search",
            "note": f"Veritabanında '{drug_name}' ile ilgili {len(results)} ilaç bulundu."
        }

    raw_result = search_drug_info(drug_name)

    if raw_result:
        summary_text = raw_result[:500].strip()
        if len(raw_result) > 500:
            last_dot = summary_text.rfind(".")
            if last_dot > 100:
                summary_text = summary_text[: last_dot + 1]

        disclaimer = "Bu bilgi web aramasından derlenmiş bir özettir, resmi prospektüs yerine geçmez."
        full_summary = f"{disclaimer}\n\n{summary_text}"

        display_name = drug_name.strip().title()
        drug_id = insert_drug(
            name=drug_name,
            display_name=display_name,
            stock=0,
            price=None,
            prospektus_summary=full_summary,
            source="fetched",
        )

        return {
            "drug_name": display_name,
            "stock": 0,
            "price": None,
            "prospektus_summary": full_summary,
            "source": "fetched_new",
            "note": "Bu ilaç veritabanına yeni eklendi, stok bilgisi güncel değildir.",
        }

    return {"error": f"'{drug_name}' ile ilgili ilaç bulunamadı. Lütfen kontrol edin."}


def create_order(drug_name: str, quantity: int | None = None) -> dict:
    if quantity is None:
        return {"error": "Sipariş miktarı belirtilmedi. Lütfen kaç adet sipariş etmek istediğinizi yazın."}

    try:
        quantity = int(quantity)
    except (ValueError, TypeError):
        return {"error": "Geçersiz sipariş miktarı. Lütfen geçerli bir sayı girin."}

    if quantity <= 0:
        return {"error": "Sipariş miktarı 0'dan büyük olmalıdır."}

    drug = find_drug(drug_name)

    if not drug:
        return {
            "error": (
                f"'{drug_name}' veritabanında kayıtlı değil. "
                "Önce get_drug_info ile ilacı sorgulayın."
            )
        }

    if drug["stock"] < quantity:
        return {
            "error": (
                f"Yetersiz stok. '{drug['display_name']}' için mevcut stok: "
                f"{drug['stock']}, istenen: {quantity}."
            )
        }

    result = create_order_record(
        drug_id=drug["id"],
        drug_name=drug["display_name"],
        quantity=quantity,
    )

    if result is None:
        return {"error": "Sipariş oluşturulamadı (stok yetersiz olabilir)."}

    return result


def check_order_status(order_id: int | None = None) -> dict:
    if order_id is None:
        return {"error": "Sipariş numarası belirtilmedi."}

    try:
        order_id = int(order_id)
    except (ValueError, TypeError):
        return {"error": "Geçersiz sipariş numarası."}

    order = find_order(order_id)

    if not order:
        return {"error": f"{order_id} numaralı sipariş bulunamadı."}

    return order


def search_by_symptom(symptom: str) -> dict:
    keyword_matches = search_drugs_by_keyword(symptom)
    if keyword_matches:
        results = [
            {
                "drug_name": d["display_name"],
                "stock": d["stock"],
                "price": d["price"],
                "prospektus_summary": d["prospektus_summary"],
            }
            for d in keyword_matches
        ]
        return {
            "symptom": symptom,
            "matching_drugs": results,
            "source": "db_keyword_search",
            "note": f"Veritabanında '{symptom}' şikayeti ile ilgili {len(results)} ilaç bulundu."
        }

    raw_result = search_drug_info(f"{symptom} tedavisi kullanılan ilaçlar")
    if raw_result:
        summary_text = raw_result[:500].strip()
        disclaimer = "Bu bilgi web aramasından derlenmiş bir özettir, resmi prospektüs yerine geçmez."
        full_summary = f"{disclaimer}\n\n{summary_text}"
        return {
            "symptom": symptom,
            "prospektus_summary": full_summary,
            "source": "web_search",
            "note": f"'{symptom}' şikayeti için web arama sonuçları derlendi."
        }

    return {"error": f"'{symptom}' şikayeti için uygun ilaç bulunamadı."}


# ---------------------------------------------------------------------------
# Tool Router
# ---------------------------------------------------------------------------

TOOL_MAP = {
    "get_drug_info": get_drug_info,
    "search_by_symptom": search_by_symptom,
    "create_order": create_order,
    "check_order_status": check_order_status,
}


def route_tool_call(tool_name: str, arguments: dict) -> dict:
    func = TOOL_MAP.get(tool_name)
    if func is None:
        return {"error": f"Tanınmayan araç: '{tool_name}'"}

    try:
        return func(**arguments)
    except TypeError as e:
        return {"error": f"Araç argüman hatası: {e}"}
    except Exception as e:
        return {"error": f"Araç çalıştırma hatası: {e}"}
