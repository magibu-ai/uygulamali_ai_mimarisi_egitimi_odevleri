# LLM'in kullanabileceği araçları tanımlayan JSON şemaları.
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_stations",
            "description": "Aktif akarsu gözlem istasyonlarını listeler. İstenirse il adına göre filtreler.",
            "parameters": {
                "type": "object",
                "properties": {
                    "province": {
                        "type": "string",
                        "description": "Filtrelemek istenen il adı (örn: Kocaeli). Boş bırakılabilir.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_latest_measurement",
            "description": "Seçilen istasyonun en güncel debi, su seviyesi ve ölçüm zamanını getirir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "station_name": {
                        "type": "string",
                        "description": "Ölçümü getirilecek istasyonun tam adı (örn: Kirazdere).",
                    }
                },
                "required": ["station_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_flow_alert",
            "description": "Belirli bir istasyon için debi eşik uyarısı oluşturur ve SQLite veritabanına yazar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "station_name": {
                        "type": "string",
                        "description": "Uyarının oluşturulacağı istasyonun adı.",
                    },
                    "threshold_m3s": {
                        "type": "number",
                        "description": "Uyarı tetiklenecek debi eşik değeri (m3/s).",
                    },
                    "note": {
                        "type": "string",
                        "description": "Uyarı için eklenecek kısa not. Kullanıcı not vermediyse boş string kullanılabilir.",
                    },
                },
                "required": ["station_name", "threshold_m3s"],
            },
        },
    },
        {
        "type": "function",
        "function": {
            "name": "create_flow_alerts",
            "description": (
                "Birden fazla veya tüm aktif akarsu gözlem istasyonları için "
                "aynı debi eşik uyarısını toplu olarak oluşturur. "
                "Kullanıcı 'tümü', 'hepsi', 'her istasyon', 'her yere' veya "
                "'bütün istasyonlar' diyorsa all_active=true kullan."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "station_names": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": (
                            "Uyarı oluşturulacak istasyon adları. "
                            "all_active=true ise boş bırakılabilir."
                        ),
                    },
                    "all_active": {
                        "type": "boolean",
                        "description": (
                            "Tüm aktif istasyonlara uyarı oluşturulacaksa true."
                        ),
                    },
                    "threshold_m3s": {
                        "type": "number",
                        "description": (
                            "Uyarı tetiklenecek debi eşik değeri (m3/s)."
                        ),
                    },
                    "note": {
                        "type": "string",
                        "description": (
                            "Uyarı için kısa not. Kullanıcı not vermediyse "
                            "boş string kullanılabilir."
                        ),
                    },
                },
                "required": ["threshold_m3s"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_flow_alerts",
            "description": "Daha önce oluşturulmuş debi uyarılarını listeler; istenirse bir istasyona göre filtreler.",
            "parameters": {
                "type": "object",
                "properties": {
                    "station_name": {
                        "type": "string",
                        "description": "Uyarıları filtrelemek için istasyon adı. Boş bırakılabilir.",
                    }
                },
            },
        },
    },
]
