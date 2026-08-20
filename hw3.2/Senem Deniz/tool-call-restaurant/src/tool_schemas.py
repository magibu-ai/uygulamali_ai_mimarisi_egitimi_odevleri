"""
tool_schemas.py
---------------
Araclarin OpenAI/HF uyumlu JSON semalari.
Bu liste hem chat_template'e (tools degiskeni) hem de InferenceClient'in
`tools` parametresine verilir. Boylece model hangi araci hangi parametrelerle
cagirabilecegini bilir.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_menu",
            "description": "Restoran menusunu getirir. Kategori verilirse filtreler.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["ana", "tatli", "icecek"],
                        "description": "Menu kategorisi (opsiyonel).",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_order",
            "description": "Musteri icin yeni bir siparis olusturur ve stoktan duser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer": {"type": "string", "description": "Musteri adi."},
                    "table_no": {"type": "integer", "description": "Masa numarasi (opsiyonel)."},
                    "items": {
                        "type": "array",
                        "description": "Siparis kalemleri.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "Menudeki urun adi."},
                                "quantity": {"type": "integer", "description": "Adet."},
                            },
                            "required": ["name", "quantity"],
                        },
                    },
                },
                "required": ["customer", "items"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_order_status",
            "description": "Verilen siparis numarasinin guncel durumunu sorgular.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer", "description": "Siparis numarasi."}
                },
                "required": ["order_id"],
            },
        },
    },
]
