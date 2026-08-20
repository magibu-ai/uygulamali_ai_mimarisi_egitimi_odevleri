"""Gradio UI for creating a personal knowledge base without technical setup."""

from __future__ import annotations

import os
import sys
import threading
import time
import uuid
from pathlib import Path

try:
    import spaces
except ImportError:
    class _LocalSpaces:
        @staticmethod
        def GPU(function=None, **_kwargs):
            def decorator(func):
                return func
            return decorator(function) if function else decorator

    spaces = _LocalSpaces()

import gradio as gr
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from dynamic_rag.knowledge.embedding import SentenceTransformerEncoder
from dynamic_rag.llm.openrouter import OpenRouterClient
from dynamic_rag.service import DynamicRagSession

IS_HF_SPACE = bool(os.getenv("SPACE_ID"))
GPU_ENCODER = SentenceTransformerEncoder(device="cuda") if IS_HF_SPACE else None
ENCODER = None
SESSIONS = {}
SESSION_LOCK = threading.Lock()
SESSION_TTL_SECONDS = 60 * 60
MAX_SESSIONS = 100
MAX_FILES = 10
MAX_FILE_BYTES = 25 * 1024 * 1024
EXAMPLE_DOCUMENT = Path(__file__).resolve().parent / "assets" / "rag_test_berk_birkan.txt"


@spaces.GPU(duration=120)
def gpu_encode_documents(texts):
    return GPU_ENCODER.encode_documents(texts)


@spaces.GPU(duration=30)
def gpu_encode_queries(texts):
    return GPU_ENCODER.encode_queries(texts)


class ZeroGPUEncoder:
    def token_count(self, text):
        return GPU_ENCODER.token_count(text)

    def encode_documents(self, texts):
        return gpu_encode_documents(texts)

    def encode_queries(self, texts):
        return gpu_encode_queries(texts)


def new_session():
    global ENCODER
    if ENCODER is None:
        ENCODER = ZeroGPUEncoder() if IS_HF_SPACE else SentenceTransformerEncoder()
    session_id = uuid.uuid4().hex
    with SESSION_LOCK:
        now = time.monotonic()
        expired = [key for key, (_, touched) in SESSIONS.items() if now - touched > SESSION_TTL_SECONDS]
        for key in expired:
            SESSIONS.pop(key, None)
        while len(SESSIONS) >= MAX_SESSIONS:
            oldest = min(SESSIONS, key=lambda key: SESSIONS[key][1])
            SESSIONS.pop(oldest, None)
        SESSIONS[session_id] = (DynamicRagSession(ENCODER), now)
    return session_id


def ensure(session_id):
    session_id = session_id or new_session()
    with SESSION_LOCK:
        entry = SESSIONS.get(session_id)
    if entry is None:
        session_id = new_session()
        entry = SESSIONS[session_id]
    session = entry[0]
    with SESSION_LOCK:
        SESSIONS[session_id] = (session, time.monotonic())
    return session_id, session


def ingest_files(files, raw_text, session_id):
    try:
        session_id, session = ensure(session_id)
        paths = [item.name if hasattr(item, "name") else item for item in (files or [])]
        if len(paths) > MAX_FILES:
            raise ValueError(f"En fazla {MAX_FILES} dosya yüklenebilir.")
        if any(Path(path).stat().st_size > MAX_FILE_BYTES for path in paths):
            raise ValueError("Her dosya en fazla 25 MB olabilir.")
        if len(raw_text or "") > 2_000_000:
            raise ValueError("Düz metin en fazla 2 milyon karakter olabilir.")
        return session.build_from_files(paths, raw_text or ""), session_id
    except Exception as exc:
        raise gr.Error(f"Bilgi tabanı oluşturulamadı: {exc}") from None


def load_example():
    """Load the bundled public-profile document into the editable text area."""
    return EXAMPLE_DOCUMENT.read_text(encoding="utf-8")


def ingest_hf(repo, split, column, max_rows, hf_token, session_id):
    try:
        session_id, session = ensure(session_id)
        limit = max(1, min(int(max_rows), 1000))
        return session.build_from_hf(repo.strip(), split.strip(), column.strip(), limit, hf_token.strip() or None), session_id
    except Exception as exc:
        raise gr.Error(f"Dataset işlenemedi: {exc}") from None


def chat(question, mode, model, key, threshold, session_id):
    with SESSION_LOCK:
        entry = SESSIONS.get(session_id)
    session = entry[0] if entry else None
    if session is None or not session.chunk_count:
        return "Önce bir bilgi tabanı oluşturun.", "Kaynak yok", "not_ready"
    try:
        return session.ask(question, mode, model.strip(), key.strip() or os.getenv("OPENROUTER_API_KEY", ""), threshold)
    except httpx.HTTPStatusError as exc:
        raise gr.Error(f"OpenRouter isteği başarısız (HTTP {exc.response.status_code}). Model erişimi, bakiye veya rate limitini kontrol edin.") from None
    except Exception as exc:
        raise gr.Error(f"Soru yanıtlanamadı: {exc}") from None


def load_models(key, free_only):
    try:
        active_key = key.strip() or os.getenv("OPENROUTER_API_KEY", "")
        choices = OpenRouterClient().list_models(active_key, free_only=free_only)
        return gr.Dropdown(choices=choices, value=choices[0][1], allow_custom_value=True)
    except httpx.HTTPStatusError as exc:
        raise gr.Error(f"Model listesi alınamadı (HTTP {exc.response.status_code}).") from None
    except Exception as exc:
        raise gr.Error(f"Model listesi alınamadı: {exc}") from None


with gr.Blocks(title="Kendi RAG Asistanını Oluştur") as demo:
    session_state = gr.State(None)
    gr.Markdown("# Kendi RAG Asistanını Oluştur\nDosyalarını veya Hugging Face veri setini ekle; geleneksel ve agentic RAG'i karşılaştır.")
    with gr.Tab("Dosya / metin"):
        files = gr.File(file_count="multiple", file_types=[".pdf", ".docx", ".csv", ".xlsx", ".md", ".txt"], label="Dosyalar")
        raw_text = gr.Textbox(lines=6, label="Veya düz metin yapıştır")
        with gr.Row():
            example_button = gr.Button("Hazır örneği kullan")
            ingest_button = gr.Button("Bilgi tabanı oluştur", variant="primary")
        gr.Markdown("*Hazır örnek, kamuya açık ve kaynaklandırılmış Berk Birkan profesyonel profilini metin alanına yükler. İçeriği inceleyip düzenleyebilirsiniz.*")
    with gr.Tab("Hugging Face Dataset"):
        repo = gr.Textbox(label="Dataset repo ID", placeholder="kullanici/dataset")
        with gr.Row():
            split = gr.Textbox(value="train", label="Split")
            column = gr.Textbox(value="text", label="Metin sütunu")
            max_rows = gr.Number(value=500, precision=0, label="Maksimum kayıt")
        hf_token = gr.Textbox(type="password", label="HF token (yalnızca gated/private dataset için)")
        hf_button = gr.Button("Dataset'ten bilgi tabanı oluştur", variant="primary")
    status = gr.Markdown("Henüz bilgi tabanı oluşturulmadı.")
    gr.Markdown("## Soru-cevap")
    with gr.Row():
        mode = gr.Radio(["Geleneksel RAG", "Agentic RAG"], value="Geleneksel RAG", label="Akış")
        model = gr.Dropdown(choices=[("OpenRouter Free Router — $0", "openrouter/free")], value="openrouter/free", allow_custom_value=True, label="OpenRouter modeli", info="Listeyi anahtarınızla yenileyebilir veya model ID'si yazabilirsiniz.")
    threshold = gr.Slider(0.0, 1.0, value=0.45, step=0.01, label="Benzerlik eşiği", info="0.45 başlangıç değeridir; kendi verinizde pozitif/negatif sorularla kalibre edin.")
    api_key = gr.Textbox(type="password", label="OpenRouter API key", info="Bellekte yalnızca bu istek için kullanılır; kaydedilmez.")
    with gr.Row():
        free_only = gr.Checkbox(value=False, label="Yalnızca ücretsiz modeller")
        models_button = gr.Button("Model listesini getir")
    question = gr.Textbox(label="Sorunuz")
    gr.Examples(
        examples=[
            ["Berk Birkan kamuya açık GitHub profilinde kendisini hangi meslekle tanımlıyor?"],
            ["Berk Birkan'ın doğum tarihi nedir?"],
        ],
        inputs=[question],
        label="Hazır belge için pozitif ve negatif örnek sorular",
    )
    ask_button = gr.Button("Sor", variant="primary")
    answer = gr.Markdown(label="Cevap")
    with gr.Accordion("Kaynaklar ve agent izi", open=False):
        citations = gr.Textbox(label="Kaynaklar")
        trace = gr.Textbox(label="Akış izi")
    example_button.click(load_example, outputs=[raw_text])
    ingest_button.click(ingest_files, [files, raw_text, session_state], [status, session_state])
    hf_button.click(ingest_hf, [repo, split, column, max_rows, hf_token, session_state], [status, session_state])
    models_button.click(load_models, [api_key, free_only], [model])
    ask_button.click(chat, [question, mode, model, api_key, threshold, session_state], [answer, citations, trace])

if __name__ == "__main__":
    demo.queue().launch(ssr_mode=False)
