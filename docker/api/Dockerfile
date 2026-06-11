FROM ghcr.io/astral-sh/uv:python3.12-trixie-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
COPY src/ src/
COPY artifacts/ artifacts/

RUN touch README.md # Needed for Hatchling
RUN uv sync --group api --no-dev --no-cache

EXPOSE 8000 9100

CMD ["uv", "run", "uvicorn", "src.credit_risk_server.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
