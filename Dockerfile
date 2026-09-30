FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 PORT=8877 \
    DEMO_STUDIO_DATA=/app/uploads/demos \
    DEMO_STUDIO_GRAPH_DB=/app/uploads/graph.sqlite \
    CRAWL_BROWSER_EXECUTABLE=/usr/bin/chromium FORWARDED_ALLOW_IPS=127.0.0.1

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates chromium ffmpeg poppler-utils tesseract-ocr fonts-liberation \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 app && useradd --uid 1000 --gid app --create-home app

WORKDIR /app
COPY requirements.txt requirements-livekit.txt requirements-lock.txt ./
RUN pip install --requirement requirements.txt --constraint requirements-lock.txt
COPY --chown=app:app server ./server
COPY --chown=app:app web ./web
COPY --chown=app:app samples ./samples
COPY --chown=app:app migrations ./migrations
RUN mkdir -p /app/uploads/demos && chown -R app:app /app/uploads

USER app
EXPOSE 8877
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8877/api/health',timeout=3)"
# The deployment sets FORWARDED_ALLOW_IPS to the one fixed Caddy container IP.
# One worker owns the bounded LiveKit bridge pool; query tokens stay out of logs.
CMD ["python", "-m", "uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8877", "--workers", "1", "--proxy-headers", "--no-access-log"]
