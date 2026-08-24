FROM ghcr.io/astral-sh/uv:0.9.10-python3.13-bookworm-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app/src

EXPOSE 8000

CMD ["uvicorn", "kiba_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
