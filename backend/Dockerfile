FROM python:3.12-slim
WORKDIR /app/backend
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HOME=/app/models FASTEMBED_CACHE_PATH=/app/models
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Download the embedding model at build time, so containers start fast.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5', cache_dir='/app/models')"
COPY . .
# Run as an ordinary user, not root: a bug in the app can't then change the container.
RUN useradd --create-home app && chown -R app /app
USER app
EXPOSE 8000
# Behind Azure's front door the visitor's real IP arrives in a header. The app reads it
# itself (guard.visitor_id, switched on with TRUSTED_PROXIES=1), so uvicorn is NOT told to
# trust proxy headers: that would let any visitor type their own "IP" and dodge the rate limit.
# --no-server-header: replies don't announce which server software this is.
CMD ["sh", "-c", "python -m pipeline init-db && uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-proxy-headers --no-server-header"]
