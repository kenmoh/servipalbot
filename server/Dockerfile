# ============================================================
# ServiPal Marketing Bot - Dockerfile
# Optimized for cheap hosting (Railway, Fly.io, Render free tier)
# ============================================================

FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies and uv
RUN apt-get update && apt-get install -y \
    gcc \
    libxml2-dev \
    libxslt-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.9.24 /uv /uvx /bin/

# Copy dependency metadata first for Docker layer caching
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
USER botuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health')"

# Start the bot
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
