"""Turkish Medical RAG — Streamlit web arayüzü (medical AI dashboard görünümü).

Çalıştırma:
    streamlit run scripts/app.py

Gerçek üretim retrieval yolunu kullanır (E5 embedding -> mevcut ChromaDB ->
top-k -> config eşiği). Bir mockup DEĞİLDİR: gerçek artifacts/chroma ve gerçek
E5 modeliyle gerçek retrieval yapar. API key yoksa çökmez; retrieval-only modda
gerçek chunk'ları gösterir. Claude yalnızca ANTHROPIC_API_KEY mevcutsa çağrılır.

Bu dosya yalnızca bir sunum katmanıdır; src/ altındaki üretim mantığını
(retrieval, embedding, threshold, RAG) değiştirmez. Görsel iyileştirmeler ve
örnek soru butonları eklenmiştir; retrieval davranışı aynıdır.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import streamlit as st

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
for _p in (str(_ROOT), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import app_logic  # noqa: E402
from app_logic import build_view_model, retrieve  # noqa: E402
from src.config import load_config, resolve_path  # noqa: E402
from src.embeddings.embedder import Embedder  # noqa: E402
from src.rag.llm import build_llm_client  # noqa: E402
from src.vectorstore.chroma_store import ChromaStore  # noqa: E402

_ASSETS = _ROOT / "assets"


@st.cache_resource(show_spinner="Model ve vektör veritabanı yükleniyor...")
def load_components():
    """Ağır bileşenleri bir kez yükler (soru başına yeniden yüklemez)."""
    config = load_config()
    embedder = Embedder.from_config(config).load()
    store = ChromaStore.from_config(config).connect(fresh=False)
    llm = build_llm_client(config)
    return config, embedder, store, llm


@st.cache_data(show_spinner=False)
def load_sidebar_stats():
    """Sidebar bilgilerini config + artifact metadata dosyalarından okur."""
    config = load_config()
    art = resolve_path(config["paths"]["artifacts"])

    def _read(name):
        path = art / name
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    ds = _read("dataset_statistics.json")
    ch = _read("chunk_statistics.json")
    em = _read("embedding_statistics.json")
    return {
        "dataset": ds.get("dataset_name", config["dataset"]["name"]),
        "documents": ds.get("selected_documents", config["dataset"]["document_count"]),
        "chunks": ch.get("chunk_count", "—"),
        "model": em.get("model_name", config["embedding"]["model_name"]),
        "dimension": em.get("embedding_dim", config["embedding"]["expected_dim"]),
        "threshold": config["retrieval"]["threshold"],
        "top_k": config["retrieval"]["top_k"],
    }


@st.cache_data(show_spinner=False)
def _svg(name: str) -> str:
    """Lokal SVG asset'ini metin olarak okur (runtime'da internet çekmez)."""
    path = _ASSETS / name
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _api_key_available(config) -> bool:
    provider = config["llm"].get("provider", "fake")
    if provider == "fake":
        return True
    key_env = config["llm"].get("api_key_env", "ANTHROPIC_API_KEY")
    return bool(os.environ.get(key_env))


_STYLE = """
<style>
  .block-container { max-width: 1120px; padding-top: 1.6rem; }
  h1 { font-weight: 750; letter-spacing: -0.5px; }
  .tmr-sub { color: #0e7490; font-weight: 600; font-size: 1.05rem; margin-top: -0.4rem; }
  .tmr-desc { color: #5b6472; font-size: 0.98rem; margin-top: 0.15rem; }
  .tmr-hero { max-width: 420px; }
  .tmr-label { font-weight: 650; color: #334155; margin: 0.4rem 0 0.2rem; }

  /* Örnek soru butonları (kart görünümü) */
  div[data-testid="stButton"] > button {
    width: 100%; text-align: left; white-space: normal; height: auto;
    border: 1px solid #d7e3ee; border-radius: 12px; background: #f8fbfe;
    padding: 0.65rem 0.85rem; font-weight: 550; color: #1f2937; line-height: 1.3;
  }
  div[data-testid="stButton"] > button:hover {
    border-color: #0e7490; background: #ecfeff; color: #0e7490;
  }
  /* Sor butonu (birincil) */
  div[data-testid="stFormSubmitButton"] > button {
    border-radius: 10px; font-weight: 650; padding: 0.5rem 1.6rem;
  }

  /* Durum bandı */
  .tmr-banner { border-radius: 12px; padding: 0.9rem 1.1rem; margin: 0.4rem 0 0.6rem;
    font-weight: 600; border-left: 6px solid; }
  .tmr-accepted { background: #ecfdf5; border-color: #059669; color: #065f46; }
  .tmr-retrieval { background: #fffbeb; border-color: #d97706; color: #92400e; }
  .tmr-rejected  { background: #fef2f2; border-color: #dc2626; color: #991b1b; }
  .tmr-banner .tmr-note { font-weight: 450; font-size: 0.92rem; margin-top: 0.25rem; }

  .tmr-section { display: flex; align-items: center; gap: 8px; margin: 0.6rem 0 0.3rem; }
  .tmr-section h3 { margin: 0; }
  .tmr-ic { width: 26px; height: 26px; }

  .tmr-chunk { border: 1px solid #e3e7ee; border-radius: 10px; padding: 0.8rem 1rem;
    background: #fbfcfe; margin-bottom: 0.6rem; }
  .tmr-chunk-meta { color: #5b6472; font-size: 0.85rem; margin-bottom: 0.35rem; }
  .tmr-chunk-title { color: #0e7490; }
  .tmr-chunk-text { font-size: 0.95rem; line-height: 1.5; white-space: pre-wrap; }
</style>
"""


def _render_chunk_card(item, show_rank=True):
    rank = f"#{item['rank']} · " if show_rank else ""
    st.markdown(
        f"<div class='tmr-chunk'>"
        f"<div class='tmr-chunk-meta'>{rank}"
        f"<b class='tmr-chunk-title'>{item['title'] or '(başlıksız)'}</b> · "
        f"kaynak: {item['source']} · benzerlik: {item['similarity']:.4f}<br>"
        f"chunk_id: {item['chunk_id']} · "
        f"<a href='{item['url']}' target='_blank'>URL</a></div>"
        f"<div class='tmr-chunk-text'>{item['chunk_text']}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def _section_heading(svg_name: str, title: str):
    st.markdown(
        f"<div class='tmr-section'><span class='tmr-ic'>{_svg(svg_name)}</span>"
        f"<h3>{title}</h3></div>",
        unsafe_allow_html=True,
    )


def render() -> None:
    st.set_page_config(page_title="Turkish Medical RAG", page_icon="🩺", layout="wide")
    st.markdown(_STYLE, unsafe_allow_html=True)

    config, embedder, store, llm = load_components()
    stats = load_sidebar_stats()
    threshold = config["retrieval"]["threshold"]
    top_k = config["retrieval"]["top_k"]
    key_available = _api_key_available(config)
    st.session_state.setdefault(app_logic.QUESTION_KEY, "")

    # --- Sidebar: System Information ---
    with st.sidebar:
        st.markdown(
            f"<div style='width:46px'>{_svg('vector_db.svg')}</div>",
            unsafe_allow_html=True,
        )
        st.header("System Information")
        st.markdown(f"**Dataset**\n\n`{stats['dataset']}`")
        st.markdown(f"**Documents:** {stats['documents']}")
        st.markdown(f"**Chunks:** {stats['chunks']}")
        st.markdown(f"**Embedding model**\n\n`{stats['model']}`")
        st.markdown(f"**Embedding dimension:** {stats['dimension']}")
        st.markdown("**Vector DB:** ChromaDB")
        st.markdown("**Similarity:** Cosine")
        st.markdown(f"**Top-k:** {stats['top_k']}")
        st.markdown(f"**Threshold:** {threshold}")
        st.divider()
        st.caption(
            "LLM: " + ("Claude API hazır"
                       if key_available and config["llm"]["provider"] != "fake"
                       else ("fake sağlayıcı" if config["llm"]["provider"] == "fake"
                             else "API key yok — retrieval-only"))
        )

    # --- Header (hero) ---
    head_left, head_right = st.columns([1.35, 1])
    with head_left:
        st.title("Turkish Medical RAG")
        st.markdown(
            "<div class='tmr-sub'>Evidence-grounded question answering over a "
            "Turkish medical corpus</div>"
            "<div class='tmr-desc'>Türkçe tıbbi içeriklerden semantik arama ve "
            "kaynaklı cevaplama</div>",
            unsafe_allow_html=True,
        )
    with head_right:
        st.markdown(f"<div class='tmr-hero'>{_svg('hero.svg')}</div>",
                    unsafe_allow_html=True)

    # --- Örnek sorular ---
    st.markdown("<div class='tmr-label'>Örnek sorular</div>", unsafe_allow_html=True)
    ex_cols = st.columns(len(app_logic.EXAMPLE_QUESTIONS))
    for col, (icon, q) in zip(ex_cols, app_logic.EXAMPLE_QUESTIONS):
        col.button(f"{icon}  {q}", key=f"ex_{q}",
                   on_click=app_logic.apply_example, args=(st.session_state, q))

    # --- Soru formu ---
    with st.form("ask"):
        question = st.text_area(
            "Soru", key=app_logic.QUESTION_KEY,
            placeholder="Örn. Anemi nedir?", height=90,
        )
        submitted = st.form_submit_button("Sor", type="primary")

    if not submitted or not question.strip():
        return

    question = question.strip()
    with st.spinner("Retrieval yapılıyor..."):
        hits = retrieve(embedder, store, top_k, question)
        try:
            view = build_view_model(
                question, hits, threshold, config["rejection_message"],
                config["rag"]["max_context_chars"],
                llm=llm, llm_available=key_available,
            )
        except Exception:
            st.warning("LLM çağrısı başarısız oldu; retrieval-only sonuç gösteriliyor.")
            view = build_view_model(
                question, hits, threshold, config["rejection_message"],
                config["rag"]["max_context_chars"], llm=None, llm_available=False,
            )

    # --- Karar / skorlar ---
    sim = view["top_similarity"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Benzerlik (top-1)", f"{sim:.4f}",
              delta=f"{sim - threshold:+.4f} eşiğe göre")
    c2.metric("Eşik (threshold)", f"{threshold}")
    c3.metric("LLM", "Çağrıldı" if view["llm_called"] else "Çağrılmadı")

    status = view["status"]
    if status == "rejected":
        st.markdown(
            f"<div class='tmr-banner tmr-rejected'>✕ Soru reddedildi — "
            f"benzerlik {sim:.4f} &lt; eşik {threshold}. LLM çağrılmadı."
            f"<div class='tmr-note'>{view['answer']}</div></div>",
            unsafe_allow_html=True,
        )
    else:
        if status == "accepted":
            st.markdown(
                "<div class='tmr-banner tmr-accepted'>✓ Soru yanıtlanabilir — "
                "Claude cevabı bağlamdan üretildi.</div>",
                unsafe_allow_html=True,
            )
            _section_heading("search.svg", "Cevap")
            st.write(view["answer"])
        else:  # retrieval_only
            st.markdown(
                "<div class='tmr-banner tmr-retrieval'>✓ Soru yanıtlanabilir — "
                "Retrieval-only mod"
                "<div class='tmr-note'>LLM API key bulunamadı. Aşağıda datasetten "
                "bulunan gerçek kaynaklar/bağlam gösteriliyor; Claude cevabı "
                "üretilmedi.</div></div>",
                unsafe_allow_html=True,
            )

        # --- Kaynaklar (kullanılan chunk'lar) ---
        _section_heading("search.svg", "Kaynaklar")
        for item in view["sources"]:
            _render_chunk_card(item, show_rank=False)

    # --- Retrieved Chunks (top-k, her zaman) ---
    with st.expander(f"Retrieved Chunks (top-{top_k})",
                     expanded=(status != "accepted")):
        for item in view["top_chunks"]:
            _render_chunk_card(item, show_rank=True)


def _running_in_streamlit() -> bool:
    try:
        from streamlit.runtime import exists
        return exists()
    except Exception:
        return True


if _running_in_streamlit():
    render()
else:  # `python scripts/app.py` ile doğrudan çalıştırılırsa yardım göster
    print("Bu bir Streamlit uygulamasıdır. Şununla çalıştırın:\n"
          "  streamlit run scripts/app.py")
