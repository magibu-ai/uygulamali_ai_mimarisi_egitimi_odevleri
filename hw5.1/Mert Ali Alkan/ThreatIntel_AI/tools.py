import html
import re
import requests
import phishing_rag
import ollama_client

TIMEOUT = 20
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

ACTIVE_EMBED_KEY = ollama_client.DEFAULT_EMBED

def internet_search(query: str = None, max_results: int = 5, **kwargs) -> str:
    """DuckDuckGo Lite üzerinden internette arama yapar. Güncel tehdit araştırması için."""
    if not query:
        query = kwargs.get("search_terms") or kwargs.get("search_term") or kwargs.get("q") or ""
        if isinstance(query, list) and len(query) > 0:
            query = query[0]
    if not query:
        return "Hata: 'query' parametresi eksik."
        
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
            title = html.unescape(re.sub(r"<[^>]+>", "", raw_title)).strip()
            if title:
                results.append(f"{len(results) + 1}. {title}\n   {html.unescape(url)}")
        if results:
            return f"'{query}' icin internet sonuclari:\n" + "\n".join(results)
    except requests.RequestException:
        pass
    return f"'{query}' icin sonuc bulunamadi."

def analyze_email(email_text: str) -> str:
    """E-postadan gönderici, alıcı, konu ve aciliyet gibi verileri çıkarır."""
    # Hem Ingilizce hem Turkce header'lari destekle
    sender_match = re.search(r"(?:From|Gönderen|Gonderen):\s*(.*)", email_text, re.IGNORECASE)
    subject_match = re.search(r"(?:Subject|Konu):\s*(.*)", email_text, re.IGNORECASE)
    
    sender = sender_match.group(1).strip() if sender_match else "Bilinmiyor"
    subject = subject_match.group(1).strip() if subject_match else "Bilinmiyor"
    
    # Kimlige Burunme (Masquerading) tespiti
    masquerading_flag = ""
    name_part = ""
    email_part = ""
    if "<" in sender and ">" in sender:
        name_part = sender.split("<")[0].strip().lower()
        email_part = sender.split("<")[1].split(">")[0].strip().lower()
    else:
        # Parantez olmadan gelen format: "Firma Adi email@domain.com"
        email_match = re.search(r'[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}', sender)
        if email_match:
            email_part = email_match.group(0).lower()
            name_part = sender[:email_match.start()].strip().lower()
    
    if name_part and email_part:
        name_words = [w for w in re.findall(r'\w+', name_part) if len(w) > 2]
        if name_words and not any(w in email_part for w in name_words):
            masquerading_flag = " [Kimlige Burunme (Masquerading) Tespit Edildi!]"
    
    urgency_words = ["urgent", "acik", "hemen", "dikkat", "warning", "hesabiniz kapatilacak", 
                     "login", "password", "acil", "askiya", "24 saat", "onemli", "iade", 
                     "dogrulama", "uyari", "askıya", "önemli", "uyarı", "doğrulama",
                     "hesabınız", "kapatılacak", "süre", "son tarih"]
    is_urgent = any(word in email_text.lower() for word in urgency_words)
    
    result = f"Gonderici: {sender}{masquerading_flag}\nKonu: {subject}\nAciliyet Iceriyor Mu?: {'Evet' if is_urgent else 'Hayir'}"
    return result

def extract_urls(email_text: str) -> str:
    """E-posta metni icindeki tum URL ve domainleri ayiklar."""
    urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', email_text)
    if not urls:
        return "E-postada URL bulunamadi."
    return "Bulunan URL'ler:\n" + "\n".join(urls)

import os
import base64
from datetime import datetime

def check_virustotal(url: str = None, **kwargs) -> str:
    """Belirtilen URL icin VirusTotal itibar sorgusu yapar."""
    urls_to_check = []
    if url:
        urls_to_check.append(url)
    
    # Eger LLM urls veya url_list gibi uyduruk isimler yollamissa tum degerleri tara
    for k, val in kwargs.items():
        if isinstance(val, list):
            for item in val:
                if isinstance(item, str) and item.startswith("http"):
                    urls_to_check.append(item)
        elif isinstance(val, str) and val.startswith("http"):
            urls_to_check.append(val)
            
    if not urls_to_check:
        return "Hata: 'url' parametresi eksik. (LLM URL'yi iletmeyi unutmus olabilir)"
        
    vt_key = os.getenv("VIRUSTOTAL_API_KEY")
    if not vt_key:
        return "VirusTotal API Key eksik. Gercek bir analiz icin .env dosyasina VIRUSTOTAL_API_KEY ekleyin."
        
    final_results = []
    for u in urls_to_check:
        try:
            # URL'yi base64url formatina ceviriyoruz
            url_id = base64.urlsafe_b64encode(u.encode()).decode().strip("=")
            headers = {"x-apikey": vt_key}
            response = requests.get(f"https://www.virustotal.com/api/v3/urls/{url_id}", headers=headers, timeout=TIMEOUT)
            
            if response.status_code == 200:
                stats = response.json().get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
                malicious = stats.get("malicious", 0)
                suspicious = stats.get("suspicious", 0)
                total = sum(stats.values())
                
                if malicious > 0 or suspicious > 0:
                    final_results.append(f"VirusTotal Sonucu: {u} icin {malicious+suspicious}/{total} guvenlik motoru 'Zararli/Supheli' isaretledi.")
                else:
                    final_results.append(f"VirusTotal Sonucu: {u} temiz. {total} guvenlik motorundan zararli kayit bulunamadi.")
                
            elif response.status_code == 404:
                final_results.append(f"VirusTotal Sonucu: {u} veritabaninda bulunamadi (onceden analiz edilmemis).")
            else:
                final_results.append(f"VirusTotal API Hatasi ({u}): {response.status_code}")
                
        except Exception as e:
            final_results.append(f"VirusTotal sorgusu sirasinda hata olustu ({u}): {e}")
            
    return "\n".join(final_results)

def _extract_root_domain(domain: str) -> str:
    """Alt domainleri atarak kok domaini cikarir."""
    # Bilinen cok parcali TLD'ler
    multi_tlds = {"co.uk", "com.br", "com.tr", "co.jp", "com.au", "co.in", "org.uk", "net.au", "gov.tr", "edu.tr"}
    parts = domain.split(".")
    if len(parts) >= 3:
        last_two = ".".join(parts[-2:])
        if last_two in multi_tlds:
            return ".".join(parts[-3:])
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return domain

def check_rdap(domain: str = None, **kwargs) -> str:
    """Belirtilen domainin public RDAP API'sinden bilgilerini getirir (kayit tarihi vb.)."""
    domains_to_check = []
    if domain:
        domains_to_check.append(domain)
        
    for k, val in kwargs.items():
        if isinstance(val, list):
            for item in val:
                if isinstance(item, str) and "." in item and not item.startswith("http"):
                    domains_to_check.append(item)
        elif isinstance(val, str) and "." in val and not val.startswith("http"):
            domains_to_check.append(val)
            
    if not domains_to_check:
        return "Hata: 'domain' parametresi eksik. (LLM Domaini iletmeyi unutmus olabilir)"
        
    final_results = []
    for d in domains_to_check:
        d_clean = d.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
        # Alt domainleri atarak kok domaini sorgula (storage.googleapis.com -> googleapis.com)
        root_domain = _extract_root_domain(d_clean)
        
        try:
            response = requests.get(f"https://rdap.org/domain/{root_domain}", headers=HEADERS, timeout=TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                events = data.get("events", [])
                registration_date = None
                
                for event in events:
                    if event.get("eventAction") == "registration":
                        registration_date = event.get("eventDate")
                        break
                        
                if registration_date:
                    # Gune cevir
                    reg_date_obj = datetime.strptime(registration_date[:10], "%Y-%m-%d")
                    days_old = (datetime.now() - reg_date_obj).days
                    
                    if days_old < 30:
                        final_results.append(f"RDAP Bilgisi: {root_domain} domaini sadece {days_old} gun once ({registration_date[:10]}) kaydedilmis. COK SUPHELI!")
                    else:
                        final_results.append(f"RDAP Bilgisi: {root_domain} uzun suredir kayitli ({days_old} gun, {registration_date[:10]}). Normal gorunuyor.")
                else:
                    final_results.append(f"RDAP Bilgisi: {root_domain} icin kayit tarihi bulunamadi, ancak kayitli bir domain.")
            else:
                if response.status_code == 404:
                    final_results.append(f"RDAP Bilgisi: {root_domain} kayitli degil veya bulunamadi (HTTP 404). Yeni veya sahte olabilir!")
                else:
                    final_results.append(f"RDAP Bilgisi: {root_domain} uzantisi desteklenmiyor veya API erisimi kapali (HTTP {response.status_code}).")
                
        except Exception as e:
            final_results.append(f"RDAP sorgusu sirasinda hata olustu ({root_domain}): {e}")
            
    return "\n".join(final_results)

def search_phishing_rag(query: str = None, **kwargs) -> str:
    """Kimlik avi analizi icin MITRE ATT&CK RAG veritabaninda arama yapar."""
    if not query:
        # LLM hangi key ile gonderirse gondersin, ilk uygun string'i yakala
        for k, val in kwargs.items():
            if isinstance(val, str) and len(val) > 5:
                query = val
                break
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, str) and len(item) > 5:
                        query = item
                        break
                if query:
                    break
            
    if not query:
        return "Hata: 'query' parametresi bulunamadi."
            
    result = phishing_rag.answer_phishing(query, embed_key=ACTIVE_EMBED_KEY)
    if not result["grounded"]:
        return result["answer"]
    sources = "\n".join(
        f"- {s['title']} (benzerlik {s['similarity']})" for s in result["sources"]
    )
    return f"{result['answer']}\n\nKaynak Taktikler:\n{sources}"

def calculate_risk_score(is_sender_suspicious: bool, has_malicious_url: bool, is_domain_new: bool, urgency: bool) -> str:
    """Belirtilen bayraklara gore deterministik risk skoru hesaplar (0-100)."""
    score = 0
    if is_sender_suspicious: score += 30
    if has_malicious_url: score += 40
    if is_domain_new: score += 20
    if urgency: score += 10
    
    category = "LOW"
    if score >= 30: category = "MEDIUM"
    if score >= 60: category = "HIGH"
    if score >= 80: category = "CRITICAL"
    
    return f"Hesaplanan Risk Skoru: {score}/100. Seviye: {category}"


TOOLS = {
    "internet_search": internet_search,
    "analyze_email": analyze_email,
    "extract_urls": extract_urls,
    "check_virustotal": check_virustotal,
    "check_rdap": check_rdap,
    "search_phishing_rag": search_phishing_rag,
    "calculate_risk_score": calculate_risk_score,
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "internet_search",
            "description": "Guncel acik kaynak siber tehdit istihbarati (OSINT) icin arama yapar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Arama sorgusu"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_email",
            "description": "Ham e-posta metninden gonderici, konu ve aciliyet gibi yapisal verileri cikarir. E-posta analizine baslarken KULLAN.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_text": {"type": "string", "description": "Kullanicinin gonderdigi tam e-posta metni"},
                },
                "required": ["email_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "extract_urls",
            "description": "E-posta metni icerisindeki linkleri ve URL'leri ayiklar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_text": {"type": "string", "description": "Kullanicinin gonderdigi tam e-posta metni"},
                },
                "required": ["email_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_virustotal",
            "description": "Bir URL'nin veya domainin VirusTotal veritabanindaki itibar (reputation) sonucunu dondurur. Birden fazla URL'yi ayni anda tarayabilirsiniz.",
            "parameters": {
                "type": "object",
                "properties": {
                    "urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Analiz edilecek URL'lerin veya domainlerin listesi"
                    },
                },
                "required": ["urls"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_rdap",
            "description": "Domainlerin kayit tarihi, yasi ve diger WHOIS/RDAP bilgilerini getirir. Yeni acilmis domainleri tespit etmek icin kullanilir. DIKKAT: Sadece e-postada GERCEKTEN gecen domainleri sorgula.",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Sorgulanacak kok domainlerin listesi (ornek: ['google.com', 'phishing.net'])"
                    },
                },
                "required": ["domain_names"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_phishing_rag",
            "description": "E-postadaki davranisin bilinen MITRE ATT&CK phishing taktikleriyle eslesip eslesmedigini bulur. DIKKAT: Teknik ID'si (T1566 gibi) yazma! Saldiri davranisini duz cumleyle anlat.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Saldiri davranisinin kisa aciklamasi (duz cumle, teknik ID kullanma)"},
                },
                "required": ["query"],
            },
        },
    },
]
