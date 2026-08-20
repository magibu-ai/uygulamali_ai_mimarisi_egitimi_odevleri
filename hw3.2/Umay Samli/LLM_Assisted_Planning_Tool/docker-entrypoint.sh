#!/bin/sh
set -eu

ollama serve >/tmp/ollama-runtime.log 2>&1 &
ollama_pid=$!

cleanup() {
    kill "$ollama_pid" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

attempts=0
until ollama list >/dev/null 2>&1; do
    attempts=$((attempts + 1))
    if ! kill -0 "$ollama_pid" 2>/dev/null; then
        echo "Ollama sunucusu beklenmedik sekilde kapandi."
        cat /tmp/ollama-runtime.log
        exit 1
    fi
    if [ "$attempts" -ge 120 ]; then
        echo "Ollama sunucusu 120 saniye icinde hazir olmadi."
        cat /tmp/ollama-runtime.log
        exit 1
    fi
    sleep 1
done

echo "Ollama hazir. $OLLAMA_MODEL modeli yukleniyor..."
ollama run "$OLLAMA_MODEL" "Yalnizca hazir yaz." >/dev/null

echo "Model hazir. Gradio uygulamasi baslatiliyor..."
python main.py
