from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from chat import kariyer_chat
from db import (
    db_baslat,
    basvuru_listele,
    basvuru_istatistikleri,
)


# =========================================================
# FASTAPI UYGULAMASI
# =========================================================

app = FastAPI(
    title="Kariyer Copilotu API",
    description="Kariyer Copilotu backend servisi",
    version="1.0.0",
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# REQUEST MODELLERİ
# =========================================================

class ChatRequest(BaseModel):
    message: str
    messages: list | None = None


# =========================================================
# BAŞLANGIÇ
# =========================================================

@app.on_event("startup")
def startup_event():
    db_baslat()


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():
    return {
        "basarili": True,
        "mesaj": "Kariyer Copilotu API çalışıyor."
    }


# =========================================================
# CHAT
# =========================================================

@app.post("/api/chat")
def chat(request: ChatRequest):

    sonuc = kariyer_chat(
        kullanici_mesaji=request.message,
        onceki_mesajlar=request.messages,
    )

    return sonuc


# =========================================================
# BAŞVURULAR
# =========================================================

@app.get("/api/basvurular")
def basvurular():

    return basvuru_listele()


# =========================================================
# İSTATİSTİKLER
# =========================================================

@app.get("/api/istatistikler")
def istatistikler():

    return basvuru_istatistikleri()