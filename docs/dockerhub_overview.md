# WireGuard Auto (WG Auto)

A professional, web-based Django application designed to automate and manage WireGuard VPN server and peer configurations. It provides an intuitive admin panel, automatic QR code generation, client configuration delivery via email, and robust asynchronous task processing using Celery.

![Admin UI](https://raw.githubusercontent.com/Tuinnov8OpenSource/wg-auto/main/docs/images/admin_preview.png)

## What is this image?

This is the official, production-ready image for **WireGuard Auto**. It is a multi-stage, hardened Docker container based on `python:3.11-slim-bookworm`, pre-loaded with `wireguard-tools`, `iproute2`, `iptables`, and [WhiteNoise](https://whitenoise.readthedocs.io/) for zero-config static file serving.

## Features

- **Automated Peer Onboarding**: Generates WireGuard configuration, keys, and QR codes automatically.
- **Email Delivery**: Delivers peer configuration details, setup guides, and QR codes via email.
- **Split-Tunneling Support**: Automatically derives and handles split-tunnel settings.
- **Background Processing**: Uses Celery to handle non-blocking asynchronous key generation safely.
- **Host Networking**: Integrates seamlessly with your host kernel to bypass Docker NAT limitations for WireGuard UDP traffic.
- **Zero-Config Static Files**: WhiteNoise serves CSS/JS/images directly from Gunicorn — no Nginx required.
- **Auto-Provisioned Admin**: Default superuser is created automatically on first boot.

---

## How to use this image

This image requires a PostgreSQL database and a Redis instance to function. The easiest and recommended way to deploy is using Docker Compose.

### 1. Create your `docker-compose.yml`
Create a file named `docker-compose.yml` on your server with the following configuration:

```yaml
version: '3.8'

services:
  web:
    image: tuinnov8/wg-auto:latest
    ports:
      - "8004:8004"
    env_file: .env
    environment:
      - DATABASE_HOST=db
      - REDIS_HOST=redis
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
    cap_add:
      - NET_ADMIN
    sysctls:
      - net.ipv4.ip_forward=1
    volumes:
      - static_data:/app/staticfiles
      - wg_config:/etc/wireguard
      - app_logs:/app/logs
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped

  celery:
    image: tuinnov8/wg-auto:latest
    command: celery -A config worker --loglevel=info --concurrency=2
    env_file: .env
    network_mode: "host"
    environment:
      - DATABASE_HOST=127.0.0.1
      - DATABASE_PORT=5432
      - REDIS_HOST=127.0.0.1
      - CELERY_BROKER_URL=redis://127.0.0.1:6379/0
      - CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0
    cap_add:
      - NET_ADMIN
    volumes:
      - wg_config:/etc/wireguard
      - app_logs:/app/logs
    restart: unless-stopped

  celery-beat:
    image: tuinnov8/wg-auto:latest
    command: celery -A config beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    env_file: .env
    environment:
      - DATABASE_HOST=db
      - REDIS_HOST=redis
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
    volumes:
      - app_logs:/app/logs
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "127.0.0.1:6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  db:
    image: postgres:15-alpine
    ports:
      - "127.0.0.1:5432:5432"
    environment:
      POSTGRES_DB: ${DATABASE_NAME:-wireguard_db}
      POSTGRES_USER: ${DATABASE_USER:-wireguard_user}
      POSTGRES_PASSWORD: ${DATABASE_PASSWORD:?DATABASE_PASSWORD must be set}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DATABASE_USER:-wireguard_user} -d ${DATABASE_NAME:-wireguard_db}"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
  redis_data:
  static_data:
  wg_config:
  app_logs:
```

### 2. Create the Environment File
Create a `.env` file in the same directory:

```env
# Core Django
DJANGO_SECRET_KEY=your-super-secret-key-change-me
DJANGO_DEBUG=False

# Cryptography (Must be exactly 32 URL-safe base64-encoded bytes)
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=your-fernet-key-here

# Database
DATABASE_NAME=wireguard_db
DATABASE_USER=wireguard_user
DATABASE_PASSWORD=your-secure-db-password

# Application Settings
WIREGUARD_ENDPOINT=vpn.yourdomain.com
```

### 3. Deploy
Start the application in the background:
```bash
docker compose up -d
```

### 4. Access the Admin Panel
A default superuser is **created automatically** on first boot:
*   **Username**: `wgauto`
*   **Password**: `wgauto123`

Navigate to `http://<your-server-ip>:8004/admin/` to log in and start managing your VPN!

> ⚠️ **Change the default password immediately after first login.** You can customize default credentials via `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_PASSWORD`, and `DJANGO_SUPERUSER_EMAIL` in your `.env` file.

---

## Architecture Note

To bypass Docker's known limitations with routing UDP packets for WireGuard, the `celery` container (which manages the WireGuard kernel interface) is configured with `network_mode: "host"`. This physically attaches the `wg1` interface to your host machine, ensuring perfect performance and handshake reliability. 

## License
MIT License. See the [GitHub Repository](https://github.com/Tuinnov8OpenSource/wg-auto) for full source code and documentation.
