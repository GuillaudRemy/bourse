FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/

# La migration est idempotente : elle cree les tables et colonnes manquantes
# sans jamais toucher aux donnees deja presentes.
CMD ["sh", "-c", "python -m backend.migrate && exec uvicorn backend.main:app --host 0.0.0.0 --port 8010"]
