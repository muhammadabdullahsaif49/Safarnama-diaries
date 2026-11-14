# ---- Safarnama Diaries: production image ----
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data \
    PORT=5000

WORKDIR /app

# Install dependencies first (better Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt "gunicorn>=22,<24"

# Run as a non-root user; /data holds the database and uploaded photos
RUN useradd --system --uid 1000 --create-home appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /data /app

COPY --chown=appuser:appuser . .

USER appuser
EXPOSE 5000

# Database + uploads live here (mount a volume on it to keep the data)
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/index.html', timeout=4).status == 200 else 1)"

# 1 worker + threads: the rate limiter keeps its counters in memory,
# so a single process keeps the limits correct.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "60", "--access-logfile", "-", "server:app"]
