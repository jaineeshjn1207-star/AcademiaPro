# ==============================================================================
# AcademiaPro Backend — Production Multi-Stage / Multi-Runtime Dockerfile
# ==============================================================================
FROM python:3.11-slim

# Prevent Python from writing .pyc files, buffer stdout/stderr, and set isolated non-root cache paths
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/appuser \
    MPLCONFIGDIR=/tmp/matplotlib \
    XDG_CACHE_HOME=/tmp/cache \
    XDG_CONFIG_HOME=/home/appuser/.config

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

# Create home, cache, media, static directories, and configure non-root user
RUN groupadd -r appuser && useradd -r -m -d /home/appuser -g appuser -u 1001 appuser && \
    mkdir -p /home/appuser/.cache /home/appuser/.config /tmp/matplotlib /tmp/cache /app/staticfiles /app/media && \
    chmod 700 /tmp/matplotlib /tmp/cache && \
    chown -R appuser:appuser /home/appuser /app /tmp/matplotlib /tmp/cache

# Switch to non-root user for safe execution
USER appuser

# Expose standard web port
EXPOSE 8000

# Health check against Django healthz endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/healthz/ || exit 1

# Run database migrations then start Gunicorn WSGI server as PID 1
CMD ["/bin/sh", "-c", "python manage.py migrate --noinput && exec gunicorn exam_portal.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --threads 2 --timeout 120"]
