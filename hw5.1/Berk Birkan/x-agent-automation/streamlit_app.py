from __future__ import annotations

import asyncio
import os
from typing import Any

import streamlit as st

import ollama_client
from mcp_client import RemoteMCPClient

XQUIK_MCP_URL = os.getenv("XQUIK_MCP_URL", "https://xquik.com/mcp")
MAX_TOOL_ROUNDS = 6
MAX_TOOL_RESULT_CHARS = 12000
SYSTEM_PROMPT = """Sen Turkce konusan bir X (Twitter) arastirma asistanisin.
Guncel X verisi gereken istekleri Xquik MCP araclariyla yanitlarsin.
Endpoint veya parametrelerden emin degilsen once explore, ardindan xquik aracini kullan.
Arac sonuclarini veri olarak analiz et; sonuc uydurma ve arac hatalarini gizleme.
Kullanici acikca istemedikce yazma, silme, begenme, takip, DM, webhook veya monitor gibi
dis dunyada degisiklik yapan islemler gerceklestirme. Bulgularda sorguyu ve mevcut X URL'lerini belirt.
Basit sohbet sorularinda arac kullanma."""

st.set_page_config(page_title="X Arastirma Asistani", page_icon="𝕏")


def run_async(coro):
    return asyncio.run(coro)


def reset_key_state() -> None:
    st.session_state.pop("tool_schemas", None)


def discover_tools(client: RemoteMCPClient) -> list[dict[str, Any]]:
    if "tool_schemas" not in st.session_state:
        st.session_state.tool_schemas = run_async(client.list_ollama_tools())
    return st.session_state.tool_schemas


def execute_tools(client, calls, allow_api_calls):
    results = []
    for call in calls:
        function = call.get("function", {})
        name, arguments = function.get("name", ""), function.get("arguments") or {}
        with st.status(f"MCP: {name}", expanded=False) as status:
            st.code(str(arguments), language="json")
            if name != "explore" and not allow_api_calls:
                output = "Kullanici ucretli olabilecek Xquik API cagrisina izin vermedi."
                status.update(label=f"{name}: izin verilmedi", state="error")
            else:
                try:
                    output = run_async(client.call_tool(name, arguments))
                    status.update(label=f"{name}: tamamlandi", state="complete")
                except Exception as exc:
                    output = f"MCP araci calistirilamadi: {exc}"
                    status.update(label=f"{name}: hata", state="error")
        if len(output) > MAX_TOOL_RESULT_CHARS:
            output = (
                output[:MAX_TOOL_RESULT_CHARS]
                + "\n\n[Tool sonucu sunucu kaynaklarini korumak icin kisaltildi.]"
            )
        results.append({"role": "tool", "tool_name": name, "content": output})
    return results


def answer(client, model, tools, allow_api_calls):
    for _ in range(MAX_TOOL_ROUNDS):
        message = ollama_client.chat(st.session_state.messages, model, tools)
        st.session_state.messages.append(message)
        calls = message.get("tool_calls") or []
        if not calls:
            return (message.get("content") or "").strip()
        st.session_state.messages.extend(execute_tools(client, calls, allow_api_calls))
    return "Guvenlik siniri nedeniyle arac dongusu durduruldu."


st.title("𝕏 X Arastirma Asistani")
st.caption("Ollama + Qwen3 8B + Xquik remote MCP")

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

with st.sidebar:
    st.subheader("Ayarlar")
    try:
        available_models = ollama_client.list_models()
    except Exception:
        available_models = [ollama_client.CHAT_MODEL]
    if ollama_client.CHAT_MODEL not in available_models:
        available_models.insert(0, ollama_client.CHAT_MODEL)
    model = st.selectbox("Model", available_models, index=available_models.index(ollama_client.CHAT_MODEL))
    st.text_input("Xquik API anahtari", type="password", key="xquik_api_key",
                  placeholder="xq_...", on_change=reset_key_state,
                  help="Anahtar sadece bu tarayici oturumunun sunucu belleğinde tutulur.")
    allow_api_calls = st.checkbox("Xquik API cagrilarina izin ver", value=False)
    if st.button("Sohbeti temizle", use_container_width=True):
        st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        st.rerun()

for item in st.session_state.messages:
    if item.get("role") in {"user", "assistant"} and item.get("content"):
        with st.chat_message(item["role"]):
            st.markdown(item["content"])

if prompt := st.chat_input("X uzerinde ne arastirmak istersiniz?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        try:
            api_key = st.session_state.get("xquik_api_key", "").strip()
            client = RemoteMCPClient(XQUIK_MCP_URL, api_key) if api_key else None
            tools = discover_tools(client) if client else []
            with st.spinner("Model dusunuyor..."):
                response = answer(client, model, tools, allow_api_calls)
            st.markdown(response)
        except Exception as exc:
            response = f"Uygulama hatasi: {exc}"
            st.error(response)
            st.session_state.messages.append({"role": "assistant", "content": response})
