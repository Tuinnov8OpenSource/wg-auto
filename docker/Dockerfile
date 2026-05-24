# ============================================================
# WireGuard Auto — Production Dockerfile
# Multi-stage build with security hardening
# ============================================================

# ── Stage 1: Build dependencies ─────────────────────────────
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Production image ───────────────────────────────
FROM python:3.11-slim

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
        wireguard-tools \
        iproute2 \
        iptables \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy Python packages from builder
COPY --from=builder /install /usr/local

# Create non-root user for the application
RUN groupadd -r wgauto && useradd -r -g wgauto -d /app -s /sbin/nologin wgauto

WORKDIR /app

# Copy application code
COPY --chown=wgauto:wgauto . .

# Create required directories
RUN mkdir -p /app/logs /app/staticfiles /app/run /etc/wireguard \
    && chown -R wgauto:wgauto /app/logs /app/staticfiles /app/run

# Remove development files from image
RUN rm -rf .env .env.local .git venv __pycache__ \
    && find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Make entrypoint executable
RUN chmod +x /app/docker/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
