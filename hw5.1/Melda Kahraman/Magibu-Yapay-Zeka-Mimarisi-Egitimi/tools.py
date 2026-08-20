import os
import math
from craft_rag import query_rag, init_rag_db
from tavily import TavilyClient

# Tavily sitesinden aldığınız API anahtarını buraya yapıştırın
TAVILY_API_KEY = "tvly-dev..."
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

try:
    init_rag_db()
except Exception:
    pass

def calculate_craft_material(width_cm: float, height_cm: float, yarn_weight: str = "medium") -> dict:
    """
    Örgü/Tığ işi projesi için gereken ip metrajını, yumak sayısını ve tığ numarasını hesaplar.
    """
    area_cm2 = round(width_cm * height_cm, 2)
    
    configs = {
        "thin": {"hook_size": "2.5 - 3.5 mm", "factor": 0.08, "meters_per_skein": 300},
        "medium": {"hook_size": "4.0 - 5.0 mm", "factor": 0.12, "meters_per_skein": 200},
        "thick": {"hook_size": "6.0 - 8.0 mm", "factor": 0.18, "meters_per_skein": 100}
    }
    
    selected_config = configs.get(yarn_weight.lower(), configs["medium"])
    
    total_meters = math.ceil(area_cm2 * selected_config["factor"])
    skeins_needed = math.ceil(total_meters / selected_config["meters_per_skein"])
    estimated_hours = round((area_cm2 / 100) * 0.4, 1)
    
    return {
        "genislik_cm": width_cm,
        "yukseklik_cm": height_cm,
        "proje_alani_cm2": area_cm2,
        "onerilen_tig_numarasi": selected_config["hook_size"],
        "toplam_ip_metresi": total_meters,
        "gereken_yumak_sayisi": skeins_needed, 
        "tahmini_sure_saat": estimated_hours
    }

def web_search(query: str) -> str:
    """
    Tavily API kullanarak örgü, amigurumi ve el sanatları odaklı Türkçe arama yapar.
    """
    try:
        
        clean_query = query.strip()
        if not any(k in clean_query.lower() for k in ["örgü", "tığ", "amigurumi"]):
            search_query = f"{clean_query} örgü tığ işi"
        else:
            search_query = clean_query
        
       
        response = tavily_client.search(
            query=search_query,
            search_depth="basic",
            max_results=2
        )
        
        results = response.get("results", [])
        
        if not results:
            return "İnternet aramasında konuyla ilgili detaylı bilgi bulunamadı."
            
        formatted_results = []
        for r in results:
            title = r.get("title", "")
            
            content = r.get("content", "")[:750] 
            formatted_results.append(f"Başlık: {title}\nÖzet: {content}")
            
        return "\n---\n".join(formatted_results)
        
    except Exception as e:
        return f"Arama hatası: {str(e)}"

def convert_yarn_units(value: float, unit_type: str) -> dict:
    """
    Yabancı örgü tariflerindeki birimleri Türk standartlarına dönüştürür.
    unit_type opsiyonları: 'oz_to_grams', 'yards_to_meters', 'inches_to_cm'
    """
    conversions = {
        "oz_to_grams": round(value * 28.3495, 2),
        "yards_to_meters": round(value * 0.9144, 2),
        "inches_to_cm": round(value * 2.54, 2)
    }
    
    converted_value = conversions.get(unit_type.lower())
    if converted_value is None:
        return {"error": "Geçersiz dönüşüm tipi. Kullanılabilirler: 'oz_to_grams', 'yards_to_meters', 'inches_to_cm'"}
    
    return {
        "original_value": value,
        "unit_type": unit_type,
        "converted_value": converted_value,
        "status": "Dönüşüm başarılı"
    }

def export_project_plan(project_title: str, plan_content: str) -> dict:
    """
    Hazırlanan örgü projesi planını veya reçetesini yerel diske .txt dosyası olarak kaydeder.
    """
    try:
        filename = f"{project_title.lower().replace(' ', '_')}_plani.txt"
        filepath = os.path.join(os.getcwd(), filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"=== {project_title.upper()} PROJE REÇETESİ ===\n\n")
            f.write(plan_content)
            
        return {
            "status": "Başarılı",
            "file_path": filepath,
            "message": f"Proje planı '{filename}' adıyla başarıyla kaydedildi."
        }
    except Exception as e:
        return {"error": f"Dosya kaydedilemedi: {str(e)}"}

def query_craft_rag(query: str) -> str:
    """
    Lokal ChromaDB vektör veritabanında teknik örgü/tığ terimlerini ve detaylarını arar.
    """
    result = query_rag(query)
    return f"[ChromaDB RAG Bilgi Bankası Sonucu]:\n{result}"

AVAILABLE_TOOLS = {
    "calculate_craft_material": calculate_craft_material,
    "web_search": web_search,
    "convert_yarn_units": convert_yarn_units,
    "export_project_plan": export_project_plan,
    "query_craft_rag": query_craft_rag
}

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "calculate_craft_material",
            "description": "Örgü veya tığ işi projeleri için gereken ip miktarını (metre/yumak) ve tığ numarasını hesaplar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "width_cm": {"type": "number", "description": "Örgünün en genişliği (cm)"},
                    "height_cm": {"type": "number", "description": "Örgünün boy yüksekliği (cm)"},
                    "yarn_weight": {
                        "type": "string", 
                        "enum": ["thin", "medium", "thick"],
                        "description": "İp kalınlığı: 'thin' (ince), 'medium' (orta), 'thick' (kalın)"
                    }
                },
                "required": ["width_cm", "height_cm"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Motif tarifleri (papatya motifi vb.), adım adım yapılışlar, güncel ip markaları, trendler ve ürün yıkama/bakım teknikleri için internette arama yapar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "İnternette aranacak Türkçe sorgu"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "convert_yarn_units",
            "description": "Yabancı tariflerdeki oz, yarda, inç ölçülerini gram, metre ve cm cinsine dönüştürür.",
            "parameters": {
                "type": "object",
                "properties": {
                    "value": {"type": "number", "description": "Dönüştürülecek sayısal değer"},
                    "unit_type": {
                        "type": "string",
                        "enum": ["oz_to_grams", "yards_to_meters", "inches_to_cm"],
                        "description": "Dönüşüm yönü"
                    }
                },
                "required": ["value", "unit_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "export_project_plan",
            "description": "Tamamlanan örgü/tığ projesi reçetesini bilgisayara .txt dosyası olarak kaydeder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_title": {"type": "string", "description": "Proje dosya başlığı"},
                    "plan_content": {"type": "string", "description": "Kaydedilecek proje talimatları, malzeme listesi ve ölçüler"}
                },
                "required": ["project_title", "plan_content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_craft_rag",
            "description": "Sadece sc, hdc, dc, inc, dec, magic ring, blocking gibi KISA ÖRGÜ TERİMLERİ ve kısaltmaların anlamını sorgular. Tarif veya motif yapımı aramaz.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Sorgulanacak örgü kısaltması veya terimi"}
                },
                "required": ["query"]
            }
        }
    }
]
