# Stage 1: Build frontend
FROM node:20-alpine AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --frozen-lockfile 2>/dev/null || npm install
COPY frontend/ .
RUN npm run build

# Stage 2: Production image
FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production

# Install nginx, Apache, and runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    apache2 \
    nginx \
    libnginx-mod-stream \
    openssl \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
WORKDIR /app
COPY backend/pyproject.toml .
RUN pip install --no-cache-dir . 2>/dev/null || pip install --no-cache-dir \
    "fastapi>=0.115" \
    "uvicorn[standard]>=0.30" \
    "sqlalchemy[asyncio]>=2.0" \
    "asyncpg>=0.30" \
    "alembic>=1.14" \
    "pydantic-settings>=2.0" \
    "authlib>=1.3" \
    "httpx>=0.27" \
    "python-jose[cryptography]>=3.3" \
    "passlib[bcrypt]>=1.7"

# Copy backend code
COPY backend/ .

# Copy frontend build output for Apache
COPY --from=frontend-build /build/dist /var/www/pikatunnel

# Copy Apache config
COPY apache/pikatunnel.conf /etc/apache2/sites-available/pikatunnel.conf

# Copy nginx configs
COPY nginx/nginx.conf /etc/nginx/nginx.conf

# Generate default self-signed cert for fallback
RUN mkdir -p /etc/nginx/ssl && \
    openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
    -keyout /etc/nginx/ssl/default.key -out /etc/nginx/ssl/default.crt \
    -subj "/CN=pikatunnel" && \
    mkdir -p /etc/nginx/proxy-routes && \
    touch /etc/nginx/nginx.stream.conf && \
    a2dissite 000-default && \
    a2ensite pikatunnel && \
    a2enmod proxy proxy_http rewrite headers && \
    sed -i 's/^Listen 80$/Listen 3000/' /etc/apache2/ports.conf

# Copy entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 80 3000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:3000/api/v1/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
