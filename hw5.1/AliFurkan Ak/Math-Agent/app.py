"""FastAPI Web Sunucusu ve Uç Noktaları (API)."""

import os
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Optional

from ollama_service import chat_with_agent, get_available_models, DEFAULT_MODEL

app = FastAPI(title="Math Agent - Ollama Client-Side Execution")

# Static dizin ve script klasörü hazırlığı
BASE_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(BASE_DIR, "static")
SCRIPTS_DIR = os.path.join(STATIC_DIR, "scripts")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(SCRIPTS_DIR, exist_ok=True)

# Statik dosyaları sun (HTML, CSS, JS, üretilen scriptler)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class ChatRequest(BaseModel):
    messages: List[Dict[str, str]]
    model: Optional[str] = DEFAULT_MODEL


@app.get("/")
def read_root():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Math Agent API çalışıyor. Arayüz için static/index.html dosyasını hazırlayın."}


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "Math Agent API"}


@app.get("/api/models")
def get_models():
    models = get_available_models()
    return {
        "models": models,
        "default": DEFAULT_MODEL if DEFAULT_MODEL in models else (models[0] if models else DEFAULT_MODEL)
    }


@app.post("/api/chat")
def chat(req: ChatRequest):
    if not req.messages:
        raise HTTPException(status_code=400, detail="Mesaj geçmişi boş olamaz.")
    
    selected_model = req.model or DEFAULT_MODEL
    response = chat_with_agent(req.messages, model=selected_model)
    return response


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
