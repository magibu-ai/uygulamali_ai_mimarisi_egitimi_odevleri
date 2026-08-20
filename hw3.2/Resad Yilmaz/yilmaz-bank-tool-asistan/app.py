from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from agent import run_bank_agent

app = FastAPI(title="Yılmaz Bank Sanal Şube Asistanı")


class QueryRequest(BaseModel):
    query: str


@app.get("/")
def serve_index():
    return FileResponse("index.html")


@app.get("/style.css")
def serve_css():
    return FileResponse("style.css")


@app.get("/app.js")
def serve_js():
    return FileResponse("app.js")


@app.post("/api/query")
def handle_query(request: QueryRequest):
    if not request.query.strip():
        return {"answer": "Lütfen bir istek yazın.", "status": {"state": "warn", "text": ""}, "trace": []}

    try:
        result = run_bank_agent(request.query.strip())
    except Exception as error:
        return {
            "answer": f"İşlem sırasında hata oluştu: {error}",
            "status": {"state": "warn", "text": str(error)},
            "trace": [],
        }

    status_text = f"{len(result['used_tools'])} tool kullanıldı: {', '.join(result['used_tools']) or 'yok'}"
    state = "warn" if result["hallucination_risk"] else "ok"
    if result["hallucination_risk"]:
        status_text = "⚠ Model tool çağırmadan cevap verdi — doğrulanmamış olabilir"

    return {"answer": result["answer"], "status": {"state": state, "text": status_text}, "trace": result["trace"]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)