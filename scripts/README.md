# WireGuard Auto: Bare-Metal Deployment Scripts

This directory contains the necessary scripts and configuration files to deploy WireGuard Auto on a bare-metal Linux server or Virtual Machine (e.g., Ubuntu/Debian) without using Docker.

## Files Overview

### 1. `install.sh`
The primary automated installation script for deploying the entire stack.

**What it does:**
- **System Preparation**: Enables required IPv4/IPv6 kernel IP forwarding.
- **User Management**: Creates a dedicated system user (`wg-auto`) and groups (`www-data`, `wireguard`) for secure execution.
- **Dependencies**: Installs necessary system packages (Python 3, PostgreSQL, Redis, WireGuard, Nginx, etc.).
- **Databases**: Automatically configures the PostgreSQL database/user and enables Redis.
- **Application Environment**: Copies the project, creates an isolated Python virtual environment (`venv`), and installs dependencies.
- **Configuration**: Generates `.env` variables securely, including `DJANGO_SECRET_KEY` and `ENCRYPTION_KEY`.
- **Initialization**: Runs Django migrations, collects static files, and securely generates initial WireGuard encryption keys for servers/peers.
- **Services setup**: Sets up an initial Django superuser, installs Supervisor for process management, and configures Nginx.

**Usage:**
```bash
sudo bash scripts/install.sh
```

### 2. `setup-sudoers.sh`
Configures secure, passwordless `sudo` access for the `wg-auto` system user. This is strictly scoped to allow the application to execute necessary `wg` and network interface commands without running the entire application as root.

**Usage (Usually handled automatically by `install.sh`):**
```bash
sudo bash scripts/setup-sudoers.sh wg-auto
```

### 3. `wg-auto-supervisor.conf`
The Supervisor configuration file that orchestrates the Python processes. It manages:
- **Gunicorn**: Serves the Django WSGI application over a Unix socket.
- **Celery Worker**: Processes asynchronous background tasks.
- **Celery Beat**: Handles periodic scheduled tasks (like log rotation or connection keepalives).

### 4. `wg-auto.conf`
The Nginx virtual host configuration. It functions as a reverse proxy, routing traffic to the Gunicorn Unix socket, and serves static/media files directly. It includes Content Security Policy (CSP) headers tailored for the administrative interface.

## Quick Start (Bare-Metal)

If you prefer running WireGuard Auto outside of Docker, simply clone the repository to your target server and run the installation script:

1. Ensure you have root privileges.
2. Run the installation script:
   ```bash
   sudo bash scripts/install.sh
   ```
3. Follow the interactive prompts to initialize your database passwords and Django superuser.
4. Once completed, your application will be available on port `80` via Nginx, and managed via `systemctl status wg-auto-supervisor`.
