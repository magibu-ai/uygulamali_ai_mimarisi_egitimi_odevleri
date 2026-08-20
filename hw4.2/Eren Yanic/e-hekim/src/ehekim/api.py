"""FastAPI application: semantic search (no key) and RAG (user-supplied key).

Security posture
----------------
* The app is served from ``127.0.0.1`` and the frontend is served by this same
  app, so there is **no CORS middleware** — cross-origin requests are simply not
  allowed by the browser's default policy.
* The provider key is read from the ``X-Provider-Key`` request header, never
  from the URL and never from a persisted field. It is used for one upstream
  call and then goes out of scope.
* A logging filter scrubs credential-shaped substrings from every record before
  a handler can format it, and every error relayed to the client passes through
  the same scrubber.
* A strict Content-Security-Policy is applied to the frontend; the page carries
  no inline script or style, so ``'unsafe-inline'`` is not needed.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import llm
from .config import (
    DEFAULT_TOP_K,
    EMBEDDING_DIM,
    EMBEDDING_MODEL_ID,
    MAX_QUERY_CHARS,
    MAX_TOP_K,
    MODEL_REFUSAL_MESSAGE_TR,
    PROJECT_ROOT,
    REFUSAL_MESSAGE_TR,
    get_settings,
)
from .embedding import Embedder, get_embedder
from .retrieval import (
    QueryError,
    build_rag_messages,
    expand_context,
    is_model_refusal,
    search,
)
from .schemas import (
    AskRequest,
    AskResponse,
    ChunkResult,
    ConfigResponse,
    ContextPassage,
    SearchRequest,
    SearchResponse,
    Usage,
)
from .security import InvalidApiKeyError, redact, validate_api_key
from .vectorstore import SearchHit, VectorStore

logger = logging.getLogger("ehekim")

FRONTEND_DIR = PROJECT_ROOT / "frontend"
API_KEY_HEADER = "X-Provider-Key"
MAX_BODY_BYTES = 64 * 1024

_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "form-action 'none'; "
    "frame-ancestors 'none'; "
    "base-uri 'none'; "
    "object-src 'none'"
)


class RedactingFilter(logging.Filter):
    """Scrub credential-shaped text from log records before they are emitted.

    Only ``str`` arguments are rewritten. Coercing every argument to a string
    would corrupt records whose format string uses a numeric specifier — for
    example uvicorn's access log, ``'%s - "%s %s HTTP/%s" %d'``, whose final
    argument is the integer status code. Turning that into ``"413"`` makes
    ``%d`` raise at format time and every access log line becomes a logging
    error instead.
    """

    @staticmethod
    def _scrub(value: object) -> object:
        return redact(value) if isinstance(value, str) else value

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._scrub(v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self._scrub(a) for a in record.args)
        return True


def install_log_redaction() -> None:
    """Attach the scrubber to the root logger and to uvicorn's loggers."""
    log_filter = RedactingFilter()
    for name in ("", "uvicorn", "uvicorn.error", "uvicorn.access", "ehekim", "openai", "httpx"):
        logging.getLogger(name).addFilter(log_filter)


class AppState:
    embedder: Embedder | None = None
    store: VectorStore | None = None


state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    install_log_redaction()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    state.store = VectorStore(settings.chroma_dir, settings.collection_name)
    count = state.store.count()
    if count == 0:
        logger.warning(
            "Vektör koleksiyonu boş (%s). Önce `python scripts/ingest.py` çalıştırın.",
            settings.chroma_dir,
        )
    else:
        logger.info("Koleksiyon hazır: %s parça.", count)

    state.embedder = get_embedder(
        device=settings.embedding_device, batch_size=settings.embedding_batch_size
    )
    logger.info("Embedding modeli yüklendi (%s).", state.embedder.device)
    yield
    state.embedder = None
    state.store = None


app = FastAPI(
    title="e-hekim",
    version="1.0.0",
    description="Türkçe tıbbi makaleler üzerinde anlamsal arama ve RAG.",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)


@app.middleware("http")
async def hardening_middleware(request: Request, call_next):
    # Reject oversized bodies before they are buffered.
    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            if int(declared) > MAX_BODY_BYTES:
                return JSONResponse({"detail": "İstek gövdesi çok büyük."}, status_code=413)
        except ValueError:
            return JSONResponse({"detail": "Geçersiz Content-Length."}, status_code=400)

    response = await call_next(request)
    response.headers["Content-Security-Policy"] = _CSP
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if request.url.path.startswith("/api/"):
        # Keys and answers must not linger in a shared cache or in bfcache.
        response.headers["Cache-Control"] = "no-store"
    return response


def get_components() -> tuple[Embedder, VectorStore]:
    if state.embedder is None or state.store is None:
        raise HTTPException(status_code=503, detail="Servis henüz hazır değil.")
    return state.embedder, state.store


def provider_key(
    x_provider_key: Annotated[str | None, Header(alias=API_KEY_HEADER)] = None,
) -> str:
    """Extract and structurally validate the caller-supplied provider key."""
    try:
        return validate_api_key(x_provider_key)
    except InvalidApiKeyError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from None


def _to_context(passages: list[SearchHit]) -> list[ContextPassage]:
    """Mirror the numbering the model was given, so [n] markers line up."""
    import math

    return [
        ContextPassage(
            citation=index,
            chunk_id=passage.chunk_id,
            chunk_text=passage.chunk_text,
            similarity=None if math.isnan(passage.similarity) else passage.similarity,
            url=passage.url,
            title=passage.title,
            source=passage.source,
            chunk_index=passage.chunk_index,
        )
        for index, passage in enumerate(passages, start=1)
    ]


def _to_results(passed: list[SearchHit], rejected: list[SearchHit]) -> list[ChunkResult]:
    out = [ChunkResult(**h.to_dict(), passed_threshold=True) for h in passed]
    out += [ChunkResult(**h.to_dict(), passed_threshold=False) for h in rejected]
    return out


@app.get("/api/health")
def health() -> dict[str, object]:
    ready = state.embedder is not None and state.store is not None
    return {"status": "ok" if ready else "starting", "chunks": state.store.count() if state.store else 0}


@app.get("/api/config", response_model=ConfigResponse)
def config() -> ConfigResponse:
    settings = get_settings()
    return ConfigResponse(
        collection=settings.collection_name,
        chunk_count=state.store.count() if state.store else 0,
        embedding_model=EMBEDDING_MODEL_ID,
        embedding_dim=EMBEDDING_DIM,
        default_threshold=settings.similarity_threshold,
        default_top_k=DEFAULT_TOP_K,
        max_top_k=MAX_TOP_K,
        max_query_chars=MAX_QUERY_CHARS,
        refusal_message=REFUSAL_MESSAGE_TR,
        model_refusal_message=MODEL_REFUSAL_MESSAGE_TR,
        default_model_key=llm.DEFAULT_MODEL_KEY,
        providers=llm.catalog(),
    )


@app.post("/api/search", response_model=SearchResponse)
def semantic_search(payload: SearchRequest) -> SearchResponse:
    """Pure vector search. Requires no API key — this is the keyless path."""
    embedder, store = get_components()
    try:
        outcome = search(
            embedder=embedder,
            store=store,
            query=payload.query,
            top_k=payload.top_k,
            threshold=payload.threshold,
        )
    except QueryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    return SearchResponse(
        query=outcome.query,
        threshold=outcome.threshold,
        top_k=payload.top_k,
        grounded=outcome.grounded,
        best_similarity=outcome.best_similarity,
        results=_to_results(outcome.hits, outcome.rejected),
        notice=None if outcome.grounded else REFUSAL_MESSAGE_TR,
    )


@app.post("/api/ask", response_model=AskResponse)
def rag_answer(
    payload: AskRequest,
    api_key: Annotated[str, Depends(provider_key)],
) -> AskResponse:
    """Retrieval-augmented answer. The key is used once and never stored."""
    embedder, store = get_components()
    settings = get_settings()

    try:
        outcome = search(
            embedder=embedder,
            store=store,
            query=payload.query,
            top_k=payload.top_k,
            threshold=payload.threshold,
        )
    except QueryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    results = _to_results(outcome.hits, outcome.rejected)

    # Threshold gate: below it, the model is never invoked, so it cannot invent
    # an answer. The refusal is produced here, by us.
    if not outcome.grounded:
        return AskResponse(
            query=outcome.query,
            threshold=outcome.threshold,
            top_k=payload.top_k,
            grounded=False,
            best_similarity=outcome.best_similarity,
            answer=REFUSAL_MESSAGE_TR,
            refused=True,
            refusal_reason="below_threshold",
            results=results,
        )

    # Expansion happens strictly after the threshold gate, so it can never turn
    # an out-of-scope question into an answered one.
    passages = expand_context(store, outcome.hits)
    messages = build_rag_messages(outcome.query, passages)
    try:
        completion = llm.generate(
            model_key=payload.model_key,
            api_key=api_key,
            messages=messages,
            timeout=settings.llm_timeout_seconds,
        )
    except llm.LLMError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from None

    # An empty completion is treated as a refusal rather than an empty answer.
    answer = completion.content or MODEL_REFUSAL_MESSAGE_TR
    # Second refusal layer: the passages cleared the similarity gate but did not
    # actually contain the answer, and the model said so instead of inventing one.
    model_refused = is_model_refusal(answer)

    return AskResponse(
        query=outcome.query,
        threshold=outcome.threshold,
        top_k=payload.top_k,
        grounded=True,
        best_similarity=outcome.best_similarity,
        answer=answer,
        refused=model_refused,
        refusal_reason="model_insufficient_context" if model_refused else None,
        model=completion.model,
        context_passages=len(passages),
        context=_to_context(passages),
        reasoning=completion.reasoning if payload.include_reasoning else None,
        usage=Usage(
            prompt_tokens=completion.prompt_tokens,
            completion_tokens=completion.completion_tokens,
            reasoning_tokens=completion.reasoning_tokens,
        ),
        results=results,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Never leak an internal message (or a credential) to the client."""
    logger.exception("İşlenmeyen hata: %s", redact(exc))
    return JSONResponse({"detail": "Sunucu hatası."}, status_code=500)


if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


def main() -> None:
    import uvicorn

    settings = get_settings()
    install_log_redaction()
    uvicorn.run(
        "ehekim.api:app",
        host=settings.host,   # 127.0.0.1 — never exposed off the machine
        port=settings.port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
