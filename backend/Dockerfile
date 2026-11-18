# Exact version for readability; the digest (a multi-arch index) makes it immutable.
FROM python:3.12.16-slim-trixie@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Unprivileged user; it may write only to /data (the database volume).
RUN useradd --system --uid 10001 --no-create-home app \
    && mkdir /data && chown app /data

# Dependencies first, so code changes don't reinstall them.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

USER app

ENV DB_PATH=/data/mini_gauntlet.db \
    INVENTORY_PATH=/app/data/inventory.json \
    SCAN_WORKERS=4

EXPOSE 8000

# python is already in the image, so no curl is needed for the health check.
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
