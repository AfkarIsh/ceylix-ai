# Multi-stage / lightweight Python base for Google Cloud Run
FROM python:3.11-slim

WORKDIR /app

# Ensure unbuffered logging & no bytecode artifacts
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install minimal OS dependencies for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy application code and benchmark fixtures
COPY backend /app/backend
COPY research /app/research

# Google Cloud Run injects PORT (defaults to 8000 locally)
ENV PORT=8000
EXPOSE 8000

# Start Uvicorn bound to 0.0.0.0 and dynamic $PORT
CMD exec uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT}
