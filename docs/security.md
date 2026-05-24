# WireGuard Auto: Security Model

## 1. Overview
Security is paramount in a VPN management system. WireGuard Auto implements defense-in-depth methodologies spanning cryptographic storage, privilege separation, network routing boundaries, and web application hardening.

## 2. Cryptographic Storage

### Fernet Encryption
Private keys (for both Servers and Peers) and SMTP passwords are never stored in plain text.
*   **Algorithm**: The application utilizes `cryptography.fernet.Fernet`, a symmetric encryption algorithm guaranteeing that a message encrypted cannot be manipulated or read without the key.
*   **Key Management**: The master `ENCRYPTION_KEY` is injected via environment variables and is never committed to the repository or stored in the database.
*   **Caching Protections**: Database models override standard retrieval methods. Decrypted keys are strictly isolated in memory per-request and are explicitly scrubbed from Redis cache payloads.

## 3. Privilege Separation

### Non-Root Execution
The Django web application and Celery workers do not run as the `root` user. They execute under the unprivileged `wgauto` (or `tisp`) user account.

### Sudoers Hardening
The application interfaces with the system's network stack via strict `sudo` rules. The `/etc/sudoers.d/` configuration restricts the application user to exclusively executing:
*   `/usr/bin/wg`
*   `/usr/bin/tee` (limited to specific paths via script wrappers)
*   `/usr/bin/chmod`

This ensures that even in the event of a Remote Code Execution (RCE) vulnerability within Django, the attacker cannot automatically gain blanket root access.

## 4. Network Security

### Split-Tunneling by Default
By default, the system enforces **Split-Tunneling**. 
*   **Mechanics**: The `AllowedIPs` configuration generated for clients is automatically restricted to the server's specific VPN subnet (e.g., `10.0.0.0/24`). 
*   **Security Benefit**: This prevents the VPN from aggressively routing all of the client's public internet traffic through the tunnel. It isolates the VPN traffic, preserving the client's internet access if the server experiences an upstream DNS or NAT routing failure.
*   **Override**: Administrators can explicitly set `0.0.0.0/0` in the Django UI if full-tunnel routing is mandated by corporate policy.

### Post-Routing & NAT
Server configurations are automatically injected with `iptables` rules utilizing modern `nftables` backends.
*   `MASQUERADE` rules are strictly bound to the specific VPN subnet and uplink interface, preventing unauthorized network bridging or IP spoofing across different local networks.

## 5. Application Security

### Header Hardening
The Django application is configured with rigorous security middleware:
*   `SECURE_BROWSER_XSS_FILTER`
*   `SECURE_CONTENT_TYPE_NOSNIFF`
*   `X_FRAME_OPTIONS = "DENY"` (Mitigates Clickjacking)

### CSRF & Session Management
*   **Trusted Origins**: Cross-Site Request Forgery protections are bound to explicitly defined `CSRF_TRUSTED_ORIGINS`.
*   **Cookie Security**: `SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE` are enforced in production, requiring HTTPS.
*   **Session Lifecycle**: Sessions are configured to expire on browser close, minimizing the window of opportunity for session hijacking.

### Password Validation
Administrative accounts are protected by Django's robust password validators, enforcing minimum length, complexity, and checking against lists of commonly compromised passwords.
