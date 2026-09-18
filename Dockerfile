# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    HOST=0.0.0.0

# Install curl for container health check
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root application user
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code and reference cases
COPY app/ app/
COPY scripts/ scripts/
COPY BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json .

# Set ownership to non-root user
RUN chown -R appuser:appuser /app
USER appuser

# Expose service port
EXPOSE 8000

# Docker healthcheck
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Start FastAPI application using Uvicorn
CMD ["sh", "-c", "uvicorn app.main:app --host ${HOST} --port ${PORT} --workers 1"]
