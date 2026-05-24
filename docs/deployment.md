# WireGuard Auto: Deployment Guide

## 1. Overview
WireGuard Auto is deployed as a containerized microservices stack using Docker Compose. The official pre-built image is available on Docker Hub at [`developerantony/wg-auto`](https://hub.docker.com/r/developerantony/wg-auto).

> [!TIP]
> The fastest way to deploy is by pulling the pre-built image directly from Docker Hub. No need to clone the repository or build locally.

## 2. Quick Start (Docker Hub Image)

### Step 1: Download configuration files
```bash
mkdir wg-auto && cd wg-auto
wget https://raw.githubusercontent.com/ngemuantony/wg-auto/main/docker-compose.yml
wget https://raw.githubusercontent.com/ngemuantony/wg-auto/main/.env.example -O .env
```

### Step 2: Configure environment
Edit the `.env` file and set your production values:
```bash
nano .env
```

**Critical variables to change:**
| Variable | Description | Example |
|---|---|---|
| `DJANGO_SECRET_KEY` | Cryptographic signing key | `django-insecure-...` (generate a random one) |
| `ENCRYPTION_KEY` | Fernet key for encrypting private keys at rest | Generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `DATABASE_PASSWORD` | PostgreSQL password | Any strong password |
| `WIREGUARD_ENDPOINT` | Public IP or domain for VPN clients | `vpn.yourdomain.com:51820` |
| `ALLOWED_HOSTS` | Comma-separated list of allowed hostnames | `yourdomain.com,your-ip` |

### Step 3: Deploy
```bash
docker compose up -d
```
This will automatically pull `developerantony/wg-auto:latest` from Docker Hub.

### Step 4: Access the Admin Panel
Navigate to `http://<your-server-ip>:8004/admin/` and log in with the default credentials:
*   **Username**: `wgauto`
*   **Password**: `wgauto123`

> [!WARNING]
> Change the default admin password immediately after first login! You can customize the default credentials via the `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_PASSWORD`, and `DJANGO_SUPERUSER_EMAIL` environment variables in your `.env` file.

## 3. Building from Source (Development)

If you are contributing to the project or need a custom build:

```bash
git clone https://github.com/ngemuantony/wg-auto.git
cd wg-auto
cp .env.example .env
# Edit .env with your settings
docker compose -f docker-compose.dev.yml up -d --build
```

## 4. Multi-Stage Docker Build

The `Dockerfile` uses a two-stage build to minimize the production image size (~450MB).

### Stage 1: Builder
*   Uses `python:3.11-slim-bookworm`.
*   Installs GCC and system headers required to compile Python C-extensions (e.g., `psycopg2`).
*   Installs Python dependencies to an isolated `/install` prefix.

### Stage 2: Production
*   Copies the pre-compiled `/install` dependencies from the builder.
*   Installs minimal runtime binaries (`wireguard-tools`, `iproute2`, `iptables`).
*   Includes [WhiteNoise](https://whitenoise.readthedocs.io/) for zero-config static file serving without Nginx.
*   Creates a non-root system user (`wgauto`).
*   Cleans up all development artifacts (`.env`, `venv`, `.git`).

## 5. Services Architecture

The `docker-compose.yml` orchestrates five services:

### 5.1. Web Service (`web`)
*   **Image**: `developerantony/wg-auto:latest`
*   **Role**: Handles inbound HTTP traffic and serves the Django Admin UI via Gunicorn.
*   **Static Files**: Served directly by WhiteNoise middleware — no Nginx required.
*   **Port**: `8004`
*   **Capabilities**: Requires `NET_ADMIN` and `net.ipv4.ip_forward=1`.

### 5.2. Celery Worker (`celery`)
*   **Image**: `developerantony/wg-auto:latest`
*   **Role**: Manages WireGuard kernel interfaces (`wg0`, `wg1`) and executes background tasks (key generation, email delivery, config sync).
*   **Networking**: Configured with `network_mode: "host"`. This is a **critical architectural requirement** — it bypasses Docker's userland proxy (`docker-proxy`), which mangles UDP headers and breaks WireGuard handshakes.
*   **Capabilities**: Requires `NET_ADMIN` to interact directly with the host's network stack.

### 5.3. Celery Beat (`celery-beat`)
*   **Role**: CRON-like scheduler using `django_celery_beat`.
*   **Function**: Manages periodic maintenance tasks and keepalive pulses.

### 5.4. PostgreSQL & Redis
*   **Role**: Stateful datastores (database and cache/message broker).
*   **Healthchecks**: Both services have strict healthchecks to prevent application containers from starting before databases are ready.

## 6. Entrypoint Behavior

On every container start, the entrypoint script automatically:
1.  Waits for the database to become available.
2.  Runs `python manage.py migrate --noinput` to apply any pending migrations.
3.  Runs `python manage.py collectstatic --noinput --clear` to compile static assets.
4.  Creates the default superuser if it doesn't already exist.
5.  Starts Gunicorn (for the `web` service) or the specified command (for Celery workers).

## 7. Persistent Volumes

State is preserved using Docker Named Volumes:
*   `postgres_data`: Database files.
*   `redis_data`: Cache and queue persistence.
*   `wg_config`: Mounted to `/etc/wireguard` to preserve generated `.conf` files.
*   `app_logs`: Centralized log aggregation for Gunicorn and Celery.
*   `static_data`: Compiled CSS/JS assets served by WhiteNoise.

## 8. Updating

To update to the latest version:
```bash
docker compose pull
docker compose up -d
```
The entrypoint will automatically run any new migrations.

## 9. Troubleshooting

| Problem | Solution |
|---|---|
| Admin UI has no styling | Ensure WhiteNoise is in `MIDDLEWARE` and `collectstatic` ran successfully. Check logs: `docker compose logs web` |
| WireGuard handshake fails | Verify the Celery container is using `network_mode: "host"` and that `ip_forward=1` is enabled on the host |
| Cannot connect to database | Check that `DATABASE_HOST` matches your setup (`db` for bridge networking, `127.0.0.1` for host networking) |
| Celery tasks not executing | Verify Redis is healthy: `docker compose exec redis redis-cli ping` |
