"""Ollama tool çağrıları için fonksiyon şema tanımları."""

MATH_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "generate_math_js",
        "description": (
            "Matematiksel bir hesaplama, denklem, matris, alan/hacim, istatistik, türev/integral, "
            "sayı dizisi veya formül istendiğinde çağrılan araç. LLM kendisi hesaplama yapmaz; "
            "bu aracı kullanarak tarayıcıda (client-side) çalıştırılacak JavaScript kodu üretir."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Üretilecek JS dosyasının adı (örnek: calculate_matrix.js, prime_factors.js)"
                },
                "description": {
                    "type": "string",
                    "description": "Hesaplama mantığının kısa ve net açıklaması"
                },
                "code": {
                    "type": "string",
                    "description": (
                        "Tarayıcıda (client-side) execute edilecek tam ve hatasız JavaScript kodu. "
                        "Kod bir fonksiyon içermeli ve doğrudan çalıştırıldığında veya çağrıldığında sonucu döndürmelidir."
                    )
                },
                "function_name": {
                    "type": "string",
                    "description": "Çağrılacak ana JS fonksiyonunun adı (opsiyonel, örn: calculateResult)"
                },
                "args": {
                    "type": "array",
                    "description": "Fonksiyona verilecek parametrelerin dizisi (örnek: [20]). Kullanıcının isteğindeki sayısal değerleri veya girdileri buraya ekleyin."
                }
            },
            "required": ["filename", "description", "code"]
        }
    }
}

MATH_WEB_SEARCH_SCHEMA = {
    "type": "function",
    "function": {
        "name": "duckduckgo_math_search",
        "description": (
            "YALNIZCA matematiksel sabitler (pi, e, yerçekimi ivmesi g, ışık hızı, dünyanın yarıçapı vb.), "
            "matematiksel formüller, geometri kuralları, finansal matematik parametreleri veya matematik tarihi "
            "hakkında canlı bilgi araştırması yapmak için kullanılan web arama aracı. "
            "Genel kültür, tarih, siyaset, magazin, spor vb. matematik dışı konularda KESİNLİKLE ÇALIŞTIRILMAZ."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Matematik veya bilimsel matematiksel bağlamdaki arama terimi (örnek: 'dünyanın yarıçapı kaç km', 'euler sayısı', 'binet formülü')"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Getirilecek maksimum sonuç sayısı (örnek: 3)"
                }
            },
            "required": ["query"]
        }
    }
}

TOOL_SCHEMAS = [MATH_TOOL_SCHEMA, MATH_WEB_SEARCH_SCHEMA]
