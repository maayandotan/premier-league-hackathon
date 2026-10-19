# One image for the whole app: the React site is built, then served by the FastAPI backend
# together with the API and the live match WebSocket.

# ---- 1. Build the website ----
FROM node:22-slim AS site
WORKDIR /srv/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- 2. The backend, serving everything ----
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    ALLOW_REAL_DATA=false
WORKDIR /srv
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/app backend/app
COPY assets/audio assets/audio
COPY data/synthetic data/synthetic
COPY --from=site /srv/frontend/dist frontend/dist

RUN useradd --create-home app
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
