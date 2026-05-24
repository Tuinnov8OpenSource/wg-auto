import logging
import ipaddress

from django.db import models
from django.core.cache import cache
from django.core.exceptions import ValidationError

from utils.crypto import CryptoService
from .constants import (
    SMTP_SETTINGS_CACHE_KEY,
    WG_ACTIVE_PEERS_CACHE_KEY,
    WG_SERVER_CACHE_KEY,
    WG_SERVER_CONFIG_CACHE_KEY_PATTERN,
)

logger = logging.getLogger(__name__)


# ============================================================
# Validators
# ============================================================

def validate_cidr(value):
    """Validate that the input is a valid IP/CIDR (IPv4 or IPv6)."""
    try:
        ipaddress.ip_interface(value)
    except ValueError:
        raise ValidationError(
            "Enter a valid IP address with CIDR (e.g., 10.10.10.1/24)"
        )


# ============================================================
# SMTP Settings
# ============================================================

class SMTPSettings(models.Model):
    host = models.CharField(
        max_length=100,
        help_text="SMTP server host (e.g., smtp.gmail.com)",
    )
    port = models.IntegerField(
        help_text="SMTP server port (e.g., 587 for TLS, 465 for SSL)",
    )
    username = models.CharField(
        max_length=100,
        help_text="SMTP authentication username (usually your email)",
    )
    password_encrypted = models.TextField(
        blank=True,
        default="",
        help_text="SMTP password (encrypted at rest)",
    )
    from_email = models.EmailField(
        help_text="The email address used as the sender (e.g., no-reply@example.com)",
    )

    def set_password(self, raw_password: str):
        """Encrypt and store the SMTP password."""
        self.password_encrypted = CryptoService.encrypt(raw_password)

    def get_password(self) -> str:
        """Decrypt and return the SMTP password."""
        if not self.password_encrypted:
            return ""
        try:
            return CryptoService.decrypt(self.password_encrypted)
        except Exception:
            logger.warning("Failed to decrypt SMTP password — may be stored in plain text")
            return self.password_encrypted

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete(SMTP_SETTINGS_CACHE_KEY)

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        cache.delete(SMTP_SETTINGS_CACHE_KEY)

    class Meta:
        verbose_name = "SMTP Setting"
        verbose_name_plural = "SMTP Settings"
        indexes = [
            models.Index(fields=["host"]),
            models.Index(fields=["username"]),
        ]


# ============================================================
# WireGuard Server
# ============================================================

class WireGuardServer(models.Model):
    name = models.CharField(
        max_length=100,
        help_text="Internal name for this server (e.g., Main Server)",
    )
    endpoint = models.CharField(
        max_length=255,
        help_text="Public endpoint (e.g., vpn.example.com:51820)",
    )
    server_address = models.CharField(
        max_length=43,
        validators=[validate_cidr],
        help_text="Server VPN IP with subnet (e.g., 10.0.0.1/24)",
    )

    private_key_encrypted = models.TextField(
        blank=True,
        default="",
        help_text="Server private key (encrypted)",
    )
    public_key = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Server public key",
    )

    interface = models.CharField(
        max_length=10,
        default="wg0",
        help_text="WireGuard network interface name (default: wg0)",
    )
    uplink_interface = models.CharField(
        max_length=15,
        default="eth0",
        help_text="Public internet facing interface for NAT (default: eth0)",
    )
    port = models.IntegerField(
        default=51820,
        help_text="Listen port for incoming VPN connections (default: 51820)",
    )

    dns = models.CharField(
        max_length=255,
        default="8.8.8.8,8.8.4.4",
        help_text="DNS servers pushed to peers (comma-separated)",
    )
    allowed_ips = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text=(
            "AllowedIPs for peer configs. Leave blank for split-tunnel "
            "(auto-derived from server subnet — recommended). "
            "Set to '0.0.0.0/0, ::/0' for full-tunnel (routes ALL traffic through VPN)."
        ),
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Enable or disable this server instance",
    )
    mtu = models.IntegerField(
        default=1420,
        help_text="Maximum Transmission Unit size (default: 1420)",
    )
    persistent_keepalive = models.IntegerField(
        default=25,
        help_text="Keepalive interval in seconds for NAT traversal (default: 25)",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # --------------------------------------------------------

    def __str__(self):
        return f"{self.name} ({self.endpoint})"

    # --------------------------------------------------------
    # Network helpers
    # --------------------------------------------------------

    def get_vpn_subnet(self) -> str:
        """
        Derive the VPN subnet CIDR from the server address.
        e.g., server_address='10.10.10.1/24' → '10.10.10.0/24'
        """
        try:
            iface = ipaddress.ip_interface(self.server_address)
            return str(iface.network)
        except ValueError:
            return "10.0.0.0/24"

    def get_effective_allowed_ips(self) -> str:
        """
        Return the AllowedIPs to use in peer configs.
        - If explicitly set, return as-is
        - If blank, auto-derive split-tunnel from server subnet
        """
        if self.allowed_ips and self.allowed_ips.strip():
            return self.allowed_ips.strip()
        return self.get_vpn_subnet()

    def next_available_ip(self) -> str:
        """
        Find the next available IP address in the server's VPN subnet.
        Skips the network address, the server's own IP, and all IPs
        already assigned to peers.
        """
        try:
            iface = ipaddress.ip_interface(self.server_address)
            network = iface.network
            server_ip = iface.ip
        except ValueError:
            raise ValueError(f"Invalid server address: {self.server_address}")

        # Collect all IPs already in use by peers on this server
        used_ips = set(
            self.peers.values_list("allowed_ip", flat=True)
        )
        used_ips.add(str(server_ip))

        for host in network.hosts():
            ip_str = str(host)
            if ip_str not in used_ips:
                return ip_str

        raise ValueError(
            f"No available IPs in subnet {network} — "
            f"{len(used_ips)} addresses already assigned"
        )

    # --------------------------------------------------------
    # Key management
    # --------------------------------------------------------

    def set_private_key(self, key: str):
        self.private_key_encrypted = CryptoService.encrypt(key)

    def get_private_key(self) -> str:
        return CryptoService.decrypt(self.private_key_encrypted)

    # --------------------------------------------------------
    # Save override (AUTO-GENERATES KEYS)
    # --------------------------------------------------------

    def save(self, *args, **kwargs):
        from .services.wireguard import WireGuardService

        private_key_missing = not self.private_key_encrypted
        public_key_missing = not self.public_key

        if private_key_missing or public_key_missing:
            try:
                private_key, public_key = WireGuardService.generate_keys()

                if not private_key or not public_key:
                    raise ValueError("WireGuard key generation returned empty values")

                self.public_key = public_key
                self.set_private_key(private_key)

            except Exception as exc:
                raise RuntimeError(
                    f"Cannot save WireGuard server '{self.name}' without valid keys"
                ) from exc

        super().save(*args, **kwargs)

        # Cache invalidation (non-fatal)
        try:
            cache.delete(WG_SERVER_CACHE_KEY)
            cache.delete(
                WG_SERVER_CONFIG_CACHE_KEY_PATTERN.format(server_id=self.id)
            )
        except Exception:
            pass

    # --------------------------------------------------------

    @classmethod
    def get_default(cls):
        cached = cache.get(WG_SERVER_CACHE_KEY)
        if cached:
            return cached

        server = cls.objects.filter(is_active=True).first()
        if server:
            cache.set(WG_SERVER_CACHE_KEY, server, timeout=None)
        return server

    def to_dict(self) -> dict:
        cache_key = WG_SERVER_CONFIG_CACHE_KEY_PATTERN.format(server_id=self.id)
        cached = cache.get(cache_key)
        if cached:
            return cached

        config = {
            "id": self.id,
            "name": self.name,
            "endpoint": self.endpoint,
            "server_address": self.server_address,
            "public_key": self.public_key,
            "interface": self.interface,
            "port": self.port,
            "dns": self.dns,
            "allowed_ips": self.get_effective_allowed_ips(),
            "mtu": self.mtu,
            "persistent_keepalive": self.persistent_keepalive,
            "is_active": self.is_active,
        }

        cache.set(cache_key, config, timeout=None)
        return config

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "WireGuard Server"
        verbose_name_plural = "WireGuard Servers"
        indexes = [
            models.Index(fields=["endpoint"]),
            models.Index(fields=["is_active"]),
        ]


# ============================================================
# WireGuard Peer
# ============================================================

class WireGuardPeer(models.Model):
    PLATFORM_CHOICES = [
        ("android", "Android"),
        ("ios", "iOS"),
        ("windows", "Windows"),
        ("linux", "Linux"),
        ("macos", "macOS"),
    ]

    name = models.CharField(
        max_length=100,
        help_text="Full name of the peer user or device",
    )
    email = models.EmailField(
        help_text="Email address to send the VPN configuration and QR code to",
    )

    server = models.ForeignKey(
        WireGuardServer,
        on_delete=models.PROTECT,
        related_name="peers",
        null=True,
        blank=True,
        help_text="The WireGuard server this peer connects to",
    )

    public_key = models.CharField(
        max_length=255,
        blank=True,
        help_text="Peer's public key (auto-generated if left blank)",
    )
    private_key_encrypted = models.TextField(
        blank=True,
        help_text="Peer's private key, encrypted at rest (auto-generated if left blank)",
    )

    allowed_ip = models.GenericIPAddressField(
        blank=True,
        null=True,
        help_text="VPN IP for this peer. Leave blank to auto-assign from the server's subnet.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Enable or disable this peer's VPN access",
    )

    allowed_ips = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text=(
            "Override AllowedIPs for this specific peer. "
            "Leave blank to inherit from server (split-tunnel recommended). "
            "Set to '0.0.0.0/0, ::/0' for full-tunnel."
        ),
    )
    dns = models.CharField(
        max_length=255,
        default="8.8.8.8,8.8.4.4",
        help_text="DNS servers assigned to this peer (comma-separated)",
    )

    platform = models.CharField(
        max_length=20,
        choices=PLATFORM_CHOICES,
        default="linux",
        help_text="Client device OS/platform",
    )

    server_endpoint = models.CharField(
        max_length=255,
        blank=True,
        help_text="Override the server endpoint for this peer (optional)",
    )
    qr_path = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="File path to the generated QR code image",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # --------------------------------------------------------

    def __str__(self):
        return f"{self.name} ({self.email})"

    def get_server(self):
        return self.server or WireGuardServer.get_default()

    def get_endpoint(self):
        return self.server_endpoint or (
            self.get_server().endpoint if self.get_server() else ""
        )

    def get_dns(self):
        return self.dns or (
            self.get_server().dns if self.get_server() else ""
        )

    def get_allowed_ips(self) -> str:
        """
        Return AllowedIPs for this peer's client config.
        Priority: peer override → server setting → auto split-tunnel from server subnet.
        """
        # Peer-level override
        if self.allowed_ips and self.allowed_ips.strip():
            return self.allowed_ips.strip()

        # Server-level setting (may also be blank for auto split-tunnel)
        server = self.get_server()
        if server:
            return server.get_effective_allowed_ips()

        return "10.0.0.0/24"

    # --------------------------------------------------------
    # Key helpers
    # --------------------------------------------------------

    def set_private_key(self, key: str):
        self.private_key_encrypted = CryptoService.encrypt(key)

    def get_private_key(self) -> str:
        return CryptoService.decrypt(self.private_key_encrypted)

    # --------------------------------------------------------

    def save(self, *args, **kwargs):
        # Auto-provision IP if not set
        if not self.allowed_ip:
            server = self.server or WireGuardServer.get_default()
            if not server:
                raise ValidationError(
                    "Cannot auto-assign IP: no server assigned and no default server found."
                )
            self.allowed_ip = server.next_available_ip()
            logger.info(
                "[IP_AUTO] Assigned %s to peer '%s' on %s",
                self.allowed_ip, self.name, server.name,
            )

        super().save(*args, **kwargs)
        cache.delete(WG_ACTIVE_PEERS_CACHE_KEY)

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        cache.delete(WG_ACTIVE_PEERS_CACHE_KEY)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "WireGuard Peer"
        verbose_name_plural = "WireGuard Peers"
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["allowed_ip"]),
            models.Index(fields=["is_active"]),
        ]
