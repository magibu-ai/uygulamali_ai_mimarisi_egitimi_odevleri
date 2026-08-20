import html
import re
import requests

TIMEOUT = 20

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def internet_search(query: str, max_results: int = 5) -> str:
    """DuckDuckGo üzerinden internette arama yapar."""

    try:
        response = requests.post(
            "https://lite.duckduckgo.com/lite/",
            data={"q": query},
            headers=HEADERS,
            timeout=TIMEOUT,
        )

        pairs = re.findall(
            r"""<a[^>]*href="([^"]+)"[^>]*class=['"]result-link['"][^>]*>(.*?)</a>""",
            response.text,
            flags=re.DOTALL,
        )

        results = []

        for url, raw_title in pairs[:max_results]:
            title = html.unescape(
                re.sub(r"<[^>]+>", "", raw_title)
            ).strip()

            if title:
                results.append(
                    f"{len(results) + 1}. {title}\n{url}"
                )

        if results:
            return (
                f"'{query}' için bulunan sonuçlar:\n"
                + "\n".join(results)
            )

        return "Arama sonucu bulunamadı."

    except requests.RequestException as exc:
        return f"İnternet araması yapılamadı: {exc}"


def grade_calculator(
    vize: float,
    final: float | None = None,
    vize_orani: float = 40,
    final_orani: float = 60,
    gecme_notu: float = 50
) -> str:
    """Öğrencinin ders ortalamasını veya gerekli final notunu hesaplar."""

    if final is None:
        gerekli_final = (
            gecme_notu - (vize * vize_orani / 100)
        ) / (final_orani / 100)

        gerekli_final = round(gerekli_final, 2)

        if gerekli_final > 100:
            return (
                f"Geçmek için finalden {gerekli_final} alman gerekiyor. "
                "Bu not 100'den büyük olduğu için bu şartlarla geçmek mümkün değil."
            )

        if gerekli_final <= 0:
            return "Mevcut vize notunla geçme notunu zaten karşılıyorsun."

        return (
            f"Geçme notu {gecme_notu}. "
            f"Finalden en az {gerekli_final} alman gerekiyor."
        )

    ortalama = (
        vize * vize_orani / 100
        + final * final_orani / 100
    )

    ortalama = round(ortalama, 2)

    if ortalama >= gecme_notu:
        durum = "Geçti"
    else:
        durum = "Kaldı"

    return (
        f"Ders ortalaması: {ortalama}. "
        f"Geçme notu: {gecme_notu}. "
        f"Durum: {durum}."
    )


TOOLS = {
    "internet_search": internet_search,
    "grade_calculator": grade_calculator,
}


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "internet_search",
            "description": (
                "Güncel bilgi, kaynak veya internet araştırması "
                "gereken sorularda internette arama yapar."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "İnternette aranacak sorgu"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Döndürülecek maksimum sonuç sayısı"
                    }
                },
                "required": ["query"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "grade_calculator",
            "description": (
                "Üniversite öğrencisinin vize ve final notlarından "
                "ders ortalamasını veya geçmek için gerekli final "
                "notunu hesaplar."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "vize": {
                        "type": "number",
                        "description": "Vize notu"
                    },
                    "final": {
                        "type": ["number", "null"],
                        "description": (
                            "Final notu. Kullanıcı finalden kaç alması "
                            "gerektiğini soruyorsa null bırak."
                        )
                    },
                    "vize_orani": {
                        "type": "number",
                        "description": "Vizenin yüzde ağırlığı. Varsayılan 40."
                    },
                    "final_orani": {
                        "type": "number",
                        "description": "Finalin yüzde ağırlığı. Varsayılan 60."
                    },
                    "gecme_notu": {
                        "type": "number",
                        "description": "Dersi geçme notu. Varsayılan 50."
                    }
                },
                "required": ["vize"]
            }
        }
    }
]