FROM python:3.13-slim-trixie AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0 EMBEDDING_CACHE_DIR=/app/models
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-install-project
COPY README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-editable
RUN /app/.venv/bin/python -c "from nevis_search.embeddings.service import load_embedder; from nevis_search.settings import get_settings; load_embedder(get_settings())" \
    && chmod -R a+rX /app/models

FROM python:3.13-slim-trixie
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/models /app/models
COPY alembic.ini ./
COPY migrations ./migrations
ENV PATH=/app/.venv/bin:$PATH EMBEDDING_CACHE_DIR=/app/models HF_HUB_OFFLINE=1 PYTHONUNBUFFERED=1
USER 10001
EXPOSE 8000
CMD ["launch"]
