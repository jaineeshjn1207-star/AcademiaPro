# ==============================================================================
# AcademiaPro Backend — Production Multi-Stage / Multi-Runtime Dockerfile
# ==============================================================================
FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Install system runtime compilers & dependencies for code execution (Python, Node, C++, Java)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    default-jdk \
    nodejs \
    npm \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . /app/

# Create media and static directories, and configure non-root user
RUN mkdir -p /app/staticfiles /app/media && \
    groupadd -r appuser && useradd -r -g appuser -u 1001 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user for safe execution
USER appuser

# Expose standard web port
EXPOSE 8000

# Health check against Django healthz endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT}/healthz/ || exit 1

# Start Gunicorn WSGI server
CMD ["sh", "-c", "gunicorn exam_portal.wsgi:application --bind 0.0.0.0:${PORT} --workers 3 --threads 2 --timeout 120"]
