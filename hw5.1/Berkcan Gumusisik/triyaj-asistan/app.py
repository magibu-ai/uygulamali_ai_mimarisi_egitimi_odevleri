"""Triyaj Asistanı — HTTP API (Flask).

Terminal sürümü (chat.py) ile AYNI beyni kullanır: aynı sistem istemi, aynı
araçlar, aynı araç-çağırma döngüsü.  Bu dosya yalnızca bir JSON API sunar;
arayüzü Next.js uygulaması (web/ klasörü) çizer ve bu API'yi çağırır.

Uçlar:
    POST /sohbet  {"mesaj": "..."}  -> {"cevap": "...", "araclar": [...]}
    POST /yeni                      -> sohbet geçmişini sıfırlar

Çalıştırmak için:
    python3 app.py            # http://localhost:5001
"""

from flask import Flask, jsonify, request

import ollama_client
import tools
from chat import SYSTEM_PROMPT, MAX_TOOL_ROUNDS

app = Flask(__name__)

# Basit tek-kullanıcılı demo için sohbet geçmişini bellekte tutarız.
# "Yeni sohbet" bunu sıfırlar.
GECMIS: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]


@app.after_request
def cors(response):
    """Next.js (farklı port) tarayıcıdan çağırabilsin diye CORS başlıkları."""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    return response


def _arac_calistir(tool_calls: list[dict]):
    """Araçları çalıştırır; modele dönecek mesajlar + arayüze gösterilecek
    çağrı bilgisini birlikte toplar."""
    tool_mesajlari = []
    ui_cagrilari = []
    for call in tool_calls:
        isim = call["function"]["name"]
        argumanlar = call["function"].get("arguments") or {}
        fonksiyon = tools.TOOLS.get(isim)
        if fonksiyon is None:
            cikti = f"'{isim}' adında bir araç yok."
        else:
            try:
                cikti = fonksiyon(**argumanlar)
            except Exception as exc:
                cikti = f"Araç çalıştırılamadı: {exc}"
        tool_mesajlari.append({"role": "tool", "tool_name": isim, "content": cikti})
        ui_cagrilari.append({"ad": isim, "arg": argumanlar, "sonuc": cikti})
    return tool_mesajlari, ui_cagrilari


@app.route("/yeni", methods=["POST", "OPTIONS"])
def yeni_sohbet():
    global GECMIS
    GECMIS = [{"role": "system", "content": SYSTEM_PROMPT}]
    return jsonify({"ok": True})


@app.route("/sohbet", methods=["POST", "OPTIONS"])
def sohbet():
    if request.method == "OPTIONS":
        return ("", 204)

    soru = (request.get_json(silent=True) or {}).get("mesaj", "").strip()
    if not soru:
        return jsonify({"cevap": "Lütfen bir mesaj yazın.", "araclar": []})

    GECMIS.append({"role": "user", "content": soru})
    kullanilan_araclar = []
    mesaj = {"content": ""}
    try:
        for _ in range(MAX_TOOL_ROUNDS):
            mesaj = ollama_client.chat(GECMIS, tools=tools.TOOL_SCHEMAS)
            GECMIS.append(mesaj)
            tool_calls = mesaj.get("tool_calls")
            if not tool_calls:
                break
            tool_mesajlari, ui_cagrilari = _arac_calistir(tool_calls)
            kullanilan_araclar.extend(ui_cagrilari)
            GECMIS.extend(tool_mesajlari)
    except RuntimeError as exc:
        return jsonify({"cevap": f"Hata: {exc}", "araclar": []})

    return jsonify(
        {"cevap": (mesaj.get("content") or "").strip(), "araclar": kullanilan_araclar}
    )


if __name__ == "__main__":
    print("Triyaj Asistanı API: http://localhost:5001")
    app.run(host="127.0.0.1", port=5001, debug=False)
