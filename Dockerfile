FROM ghcr.io/astral-sh/uv:python3.12-trixie-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    libgomp1 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH="/home/user/.local/bin:$PATH"
WORKDIR $HOME/app

COPY --chown=user pyproject.toml uv.lock ./
COPY --chown=user src/ src/

ARG MODEL_TAG=model-inference-v0.1.0
RUN mkdir -p artifacts && \
    for tier in prod dev debug; do \
      curl -fsSL "https://github.com/lucasdlb/oc-p6/releases/download/${MODEL_TAG}/inference_pipeline_${tier}.pkl" \
        -o artifacts/inference_pipeline.pkl && break; \
    done

RUN touch README.md
RUN uv sync --group api --no-dev --no-cache

EXPOSE 8000 9100

CMD ["uv", "run", "uvicorn", "src.credit_risk_server.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
