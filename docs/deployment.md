# WireGuard Auto: Deployment Guide

## 1. Overview
WireGuard Auto is primarily deployed using a containerized microservices architecture via Docker and Docker Compose. This ensures environment parity, strict dependency management, and high availability.

> [!NOTE]
> For bare-metal or VM deployments without Docker, refer to the [Scripts Deployment Guide](../scripts/README.md).

## 2. Multi-Stage Docker Build
The application utilizes a `Dockerfile` with multi-stage compilation to minimize the production image footprint and enhance security.

### Stage 1: Builder
*   Uses `python:3.11-slim`.
*   Installs GCC and system headers required to compile Python C-extensions (e.g., `psycopg2`).
*   Installs Python dependencies to an isolated `/install` prefix.

### Stage 2: Production
*   Copies the pre-compiled `/install` dependencies.
*   Installs minimal runtime binaries (`wireguard-tools`, `iproute2`, `iptables`).
*   Creates a non-root system user (`wgauto`).
*   Cleans up all development artifacts (`.env`, `venv`, `.git`).

## 3. Services Configuration

The `docker-compose.yml` orchestrates five isolated services.

### 3.1. Web Service
*   **Role**: Handles inbound HTTP traffic and serves the Django Administrative UI.
*   **Server**: Gunicorn WSGI HTTP Server.
*   **Networking**: Requires `NET_ADMIN` capabilities and `net.ipv4.ip_forward=1` to manage the WireGuard interface routing.

### 3.2. Celery Worker
*   **Role**: Executes long-running tasks and strictly manages the WireGuard kernel interfaces (`wg0`, `wg1`).
*   **Networking**: Configured with `network_mode: "host"`. This is a critical architectural requirement. It bypasses Docker's internal userland proxy (`docker-proxy`), which is known to mangle UDP headers and source IPs, preventing WireGuard handshakes.
*   **Capabilities**: Requires `NET_ADMIN` capabilities to interact directly with the host machine's physical network stack and execute `wg-quick`.

### 3.3. Celery Beat
*   **Role**: CRON-like scheduler utilizing `django_celery_beat`.
*   **Function**: Manages periodic maintenance tasks, log rotation, and keepalive pulses.

### 3.4. PostgreSQL & Redis
*   **Role**: Stateful datastores.
*   **Healthchecks**: Both services feature rigid healthchecks to ensure the Web and Celery containers do not initialize before the databases are ready to accept connections.

## 4. Environment Configuration
The system relies on a strictly typed `.env` file mounted into the containers at runtime. 

### Critical Variables
*   `DJANGO_SECRET_KEY`: Cryptographic signing key for Django sessions.
*   `ENCRYPTION_KEY`: A 32-byte URL-safe base64-encoded string used by the `Fernet` symmetric encryption algorithm to secure Private Keys at rest.
*   `WIREGUARD_ENDPOINT`: The public-facing IP or Domain mapping to the server.

## 5. Network Configuration & Capabilities

To allow the containers to establish and route a VPN tunnel, elevated privileges are mapped to the specific containers that need them:
*   `cap_add: [NET_ADMIN]`: Allows the container to interact with network interfaces, modify routing tables, and bind to restricted ports.
*   `sysctls: [net.ipv4.ip_forward=1]`: Enables IP forwarding at the kernel level within the container's network namespace, permitting traffic to route from the VPN subnet to the public internet interface.

## 6. Persistent Volumes
State is preserved using Docker Named Volumes:
*   `postgres_data`: Database files.
*   `redis_data`: Cache and queue persistence.
*   `wg_config`: Mounted to `/etc/wireguard` to preserve generated `.conf` files.
*   `app_logs`: Centralized log aggregation for Gunicorn and Celery.
*   `static_data`: Compiled CSS/JS assets served by the Nginx reverse proxy.
