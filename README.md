# WireGuard Auto (WG Auto)

A professional, web-based Django application designed to automate and manage WireGuard VPN server and peer configurations. It provides an intuitive admin panel, automatic QR code generation, client configuration delivery via email, and robust asynchronous task processing using Celery.

![WireGuard Auto Admin Interface](docs/images/admin_preview.png)

## Features

- **Automated Peer Onboarding**: Generates WireGuard configuration, keys, and QR codes automatically.
- **Email Delivery**: Delivers peer configuration details, setup guides, and QR codes via email.
- **Split-Tunneling Support**: Automatically derives and handles split-tunnel settings for routing specific subnets.
- **Platform-Specific Guides**: Generates Markdown-based configuration guides for Windows, macOS, Linux, Android, and iOS clients.
- **Robust Background Processing**: Uses Celery and Redis to handle non-blocking asynchronous key generation and configuration application securely.
- **Professional Admin UI**: Uses Django Jazzmin for a clean, responsive, and highly professional administrative interface.
- **Production-Ready Docker**: Fully containerized using multi-stage builds, Gunicorn, PostgreSQL, and Nginx reverse proxy capabilities.

## Requirements

- Docker & Docker Compose
- Or standard Linux environment with Python 3.11+, PostgreSQL, Redis, and `wireguard-tools`.

## Installation

### Option 1: Docker (Recommended)

The fastest and most stable way to deploy WireGuard Auto is using our official pre-built Docker image (`tuinnov8/wg-auto:latest`). You do not need to clone the repository.

1. Download the production configuration files:
   ```bash
   wget https://raw.githubusercontent.com/Tuinnov8OpenSource/wg-auto/main/docker-compose.yml
   wget https://raw.githubusercontent.com/Tuinnov8OpenSource/wg-auto/main/.env.example -O .env
   ```
2. Configure your environment variables (securely set `DATABASE_PASSWORD`, `DJANGO_SECRET_KEY`, and `ENCRYPTION_KEY`):
   ```bash
   nano .env
   ```
3. Bring up the containers (this will automatically pull the image from Docker Hub):
   ```bash
   docker compose up -d
   ```
4. Access the application at `http://<your-server-ip>:8004/admin/` with the default credentials (`wgauto` / `wgauto123`).

### Option 2: Bare Metal / VM (Without Docker)

If you prefer to run the application directly on your host operating system (Ubuntu/Debian) utilizing Nginx, PostgreSQL, Redis, and Supervisor, you can use our automated install script.

1. Clone the repository and navigate into it:
   ```bash
   git clone https://github.com/Tuinnov8OpenSource/wg-auto.git
   cd wg-auto
   ```
2. Run the bare-metal installation script as root:
   ```bash
   sudo bash scripts/install.sh
   ```
   *(This script will install all dependencies, configure databases, setup Gunicorn/Celery under Supervisor, and route traffic through Nginx).*

## Security

- Private keys and SMTP passwords are encrypted at rest using Fernet encryption.
- Multi-stage Docker build avoids leaving build dependencies in production images.
- System processes execute commands with restricted `sudo` rules to maintain server isolation.

## Contribution

We welcome contributions! Please review our [Contributing Guide](CONTRIBUTING.md) to get started.

## License

This project is open-source and released under the [MIT License](LICENSE).
