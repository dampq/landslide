FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home backend && mkdir /data && chown backend:backend /data
COPY --chown=backend:backend . .
ENV DATABASE_PATH=/data/backend.sqlite3 PYTHONUNBUFFERED=1
USER backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["waitress-serve", "--listen=0.0.0.0:8000", "--threads=8", "--max-request-body-size=14100000", "app:application"]
