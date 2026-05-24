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

## Installation (Docker)

1. Clone the repository.
2. Run `cp .env.example .env` and customize your settings, especially the `DATABASE_PASSWORD`, `DJANGO_SECRET_KEY`, and `ENCRYPTION_KEY`.
3. Bring up the containers:
   ```bash
   docker-compose up -d --build
   ```
4. Access the application on port `8004`.

## Security

- Private keys and SMTP passwords are encrypted at rest using Fernet encryption.
- Multi-stage Docker build avoids leaving build dependencies in production images.
- System processes execute commands with restricted `sudo` rules to maintain server isolation.

## Contribution

We welcome contributions! Please review our [Contributing Guide](CONTRIBUTING.md) to get started.

## License

This project is open-source and released under the [MIT License](LICENSE).
