FROM ghcr.io/astral-sh/uv:python3.12-trixie-slim

RUN uv pip install --system --no-cache evidently==0.7.21 \
    && useradd --create-home appuser

USER appuser
WORKDIR /workspace

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501')" || exit 1

CMD ["evidently", "ui", "--host", "0.0.0.0", "--port", "8501", "--workspace", "/workspace"]
