FROM ollama/ollama:latest AS ollama-runtime

RUN rm -rf /usr/lib/ollama/cuda_v12 /usr/lib/ollama/cuda_v13 /usr/lib/ollama/mlx_cuda_v13 /usr/lib/ollama/vulkan

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    OLLAMA_MODEL=llama3.2:3b \
    OLLAMA_HOST=127.0.0.1:11434 \
    OLLAMA_BASE_URL=http://127.0.0.1:11434 \
    OLLAMA_MODELS=/home/user/.ollama/models \
    PATH=/home/user/app/.venv/bin:$PATH \
    OLLAMA_NUM_PARALLEL=1 \
    OLLAMA_MAX_LOADED_MODELS=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=7860

COPY --from=ollama-runtime /usr/bin/ollama /usr/bin/ollama
COPY --from=ollama-runtime /usr/lib/ollama /usr/lib/ollama

RUN apt-get update && \
    apt-get install --yes --no-install-recommends fonts-dejavu-core && \
    rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 user
WORKDIR /home/user/app

COPY --chown=user:user pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev

COPY --chown=user:user . .
RUN chmod +x docker-entrypoint.sh && \
    install -d -o user -g user /home/user/.ollama && \
    install -d -o user -g user /home/user/.ollama/models && \
    install -d -o user -g user /home/user/app/data
USER user

RUN set -eu; \
    ollama serve >/tmp/ollama-build.log 2>&1 & \
    server_pid=$!; \
    attempts=0; \
    until ollama list >/dev/null 2>&1; do \
        attempts=$((attempts + 1)); \
        if ! kill -0 "$server_pid" 2>/dev/null; then \
            echo "Ollama build sirasinda beklenmedik sekilde kapandi."; \
            cat /tmp/ollama-build.log; \
            exit 1; \
        fi; \
        if [ "$attempts" -ge 120 ]; then \
            echo "Ollama 120 saniye icinde hazir olmadi."; \
            cat /tmp/ollama-build.log; \
            kill "$server_pid" 2>/dev/null || true; \
            exit 1; \
        fi; \
        sleep 1; \
    done; \
    echo "Ollama hazir. $OLLAMA_MODEL modeli indiriliyor..."; \
    ollama pull "$OLLAMA_MODEL"; \
    kill "$server_pid"; \
    wait "$server_pid" 2>/dev/null || true

EXPOSE 7860
CMD ["./docker-entrypoint.sh"]
