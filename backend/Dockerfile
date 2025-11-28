FROM python:3.11-slim

WORKDIR /app

# Install build + runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libpq-dev libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install dependencies with cache (chi rebuild khi requirements thay doi)
COPY requirements-ml.txt requirements-base.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements-ml.txt && \
    pip install --no-cache-dir -r requirements-base.txt

# Copy code (volume mount se override trong dev mode)
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Default: dev mode with reload (production se override)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
