import ipaddress

from django import forms
from django.contrib import admin, messages
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import WireGuardPeer, SMTPSettings, WireGuardServer


# ============================================================
# SERVER ADMIN
# ============================================================

class WireGuardServerForm(forms.ModelForm):
    """Custom form with validation for server fields."""

    class Meta:
        model = WireGuardServer
        fields = "__all__"

    def clean_endpoint(self):
        endpoint = self.cleaned_data.get("endpoint", "").strip()
        if not endpoint:
            raise forms.ValidationError("Endpoint is required.")

        # Strip trailing dots
        host = endpoint.split(":")[0].strip().rstrip(".")
        if not host:
            raise forms.ValidationError("Endpoint host cannot be empty.")

        # Warn if using a private/VPN IP as endpoint
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private:
                raise forms.ValidationError(
                    f"Endpoint '{host}' is a private IP address. "
                    "The endpoint must be your PUBLIC IP or domain name "
                    "(e.g., vpn.example.com or 203.0.113.5)."
                )
        except ValueError:
            # Not an IP — likely a domain name, which is fine
            pass

        # Normalize: store as host:port or just host (no trailing dots)
        parts = endpoint.split(":")
        cleaned = host
        if len(parts) > 1 and parts[1].strip():
            cleaned = f"{host}:{parts[1].strip()}"
        return cleaned

    def clean_server_address(self):
        value = self.cleaned_data.get("server_address", "").strip()
        if not value:
            raise forms.ValidationError("Server address is required.")

        try:
            iface = ipaddress.ip_interface(value)
        except ValueError:
            raise forms.ValidationError(
                f"'{value}' is not a valid IP/CIDR. Example: 10.10.10.1/24"
            )

        # Reject network address (e.g., 10.10.10.0/24)
        if iface.ip == iface.network.network_address:
            raise forms.ValidationError(
                f"'{value}' is a network address, not a host address. "
                f"The server needs a host IP like '{next(iface.network.hosts())}/{iface.network.prefixlen}'."
            )

        # Reject broadcast address
        if iface.ip == iface.network.broadcast_address:
            raise forms.ValidationError(
                f"'{value}' is the broadcast address. Use a host IP instead."
            )

        return value


@admin.register(WireGuardServer)
class WireGuardServerAdmin(admin.ModelAdmin):
    form = WireGuardServerForm
    list_display = (
        "name", "endpoint_display", "interface", "uplink_interface",
        "port", "is_active_badge", "peer_count", "has_keys", "updated_at",
    )
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "endpoint")
    readonly_fields = (
        "public_key_display", "private_key_display",
        "created_at", "updated_at", "regenerate_keys_button",
        "config_preview",
    )
    fieldsets = (
        ("Basic Info", {
            "fields": ("name", "endpoint", "is_active"),
        }),
        ("Network Configuration", {
            "fields": ("interface", "uplink_interface", "port", "server_address", "mtu"),
        }),
        ("Keys", {
            "fields": ("public_key_display", "private_key_display", "regenerate_keys_button"),
            "classes": ("collapse",),
            "description": "Keys are auto-generated on creation. Click regenerate to create new keys.",
        }),
        ("Client Defaults", {
            "fields": ("dns", "allowed_ips", "persistent_keepalive"),
        }),
        ("Server Config Preview", {
            "fields": ("config_preview",),
            "classes": ("collapse",),
            "description": "Live preview of the generated WireGuard server configuration.",
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing existing server
            return self.readonly_fields + ("interface", "port", "server_address")
        return self.readonly_fields

    # -- List display helpers --

    def endpoint_display(self, obj):
        endpoint = obj.endpoint or "—"
        # Highlight if endpoint looks wrong (private IP or has trailing dot)
        host = endpoint.split(":")[0].rstrip(".")
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private:
                return format_html(
                    '<span style="color: #dc3545;" title="Private IP — should be public">'
                    '⚠️ {}</span>', endpoint
                )
        except ValueError:
            pass
        return endpoint
    endpoint_display.short_description = "Endpoint"
    endpoint_display.admin_order_field = "endpoint"

    def is_active_badge(self, obj):
        if obj.is_active:
            return mark_safe(
                '<span style="background:#198754;color:#fff;padding:3px 10px;'
                'border-radius:12px;font-size:0.8em;font-weight:600;">Active</span>'
            )
        return mark_safe(
            '<span style="background:#6c757d;color:#fff;padding:3px 10px;'
            'border-radius:12px;font-size:0.8em;font-weight:600;">Inactive</span>'
        )
    is_active_badge.short_description = "Status"
    is_active_badge.admin_order_field = "is_active"

    def peer_count(self, obj):
        total = obj.peers.count()
        active = obj.peers.filter(is_active=True).count()
        if total == 0:
            return mark_safe('<span style="color:#999;">0 peers</span>')
        return format_html(
            '<span title="{} active / {} total" style="font-weight:600;">'
            '{} / {}</span>',
            active, total, active, total,
        )
    peer_count.short_description = "Peers (Active/Total)"

    def has_keys(self, obj):
        if obj.private_key_encrypted and obj.private_key_encrypted != "-" and len(obj.private_key_encrypted) > 10:
            return mark_safe(
                '<span style="color:#198754;font-weight:600;">✓ Present</span>'
            )
        return mark_safe(
            '<span style="color:#dc3545;font-weight:600;">✗ Missing</span>'
        )
    has_keys.short_description = "Keys"

    # -- Detail display helpers --

    def public_key_display(self, obj):
        if not obj or not obj.pk:
            return mark_safe(
                '<em style="color: #e67e22;">Not generated yet (will be created on save)</em>'
            )
        if not obj.public_key or obj.public_key == "-":
            return mark_safe('<em style="color: #e67e22;">Not generated yet</em>')
        return format_html(
            '<code style="word-break:break-all;display:block;padding:10px;'
            'background:#1a1a2e;color:#0ff;border-radius:6px;font-family:monospace;">'
            '{}</code>',
            obj.public_key,
        )
    public_key_display.short_description = "Server Public Key"

    def private_key_display(self, obj):
        if not obj or not obj.pk:
            return mark_safe(
                '<em style="color: #e67e22;">Not generated yet (will be created on save)</em>'
            )
        if not obj.private_key_encrypted or obj.private_key_encrypted == "-":
            return mark_safe('<em style="color: #e67e22;">Not generated yet</em>')
        return format_html(
            '<div style="padding:12px;background:#1a1a2e;border-radius:6px;'
            'color:#e0e0e0;border-left:4px solid #198754;">'
            '<strong style="color:#0ff;">Status:</strong> 🔒 Encrypted and stored securely<br>'
            '<strong style="color:#0ff;">Length:</strong> {} characters<br>'
            '<em style="color:#888;">Private key is never displayed for security reasons.</em>'
            '</div>',
            len(obj.private_key_encrypted),
        )
    private_key_display.short_description = "Server Private Key (Encrypted)"

    def regenerate_keys_button(self, obj):
        if not obj or not obj.pk:
            return mark_safe('<em>Keys will be auto-generated when you save this server.</em>')
        return format_html(
            '<div style="padding:12px;background:#1a1a2e;border-radius:6px;'
            'border-left:4px solid #0d6efd;color:#e0e0e0;">'
            '<strong style="color:#0ff;">To regenerate keys:</strong><br>'
            '1. Save the server (auto-generates missing keys)<br>'
            '2. Or use: <code style="color:#0ff;">python manage.py regenerate_server_keys {}</code>'
            '</div>',
            obj.pk,
        )
    regenerate_keys_button.short_description = "Key Management"

    def config_preview(self, obj):
        """Show a live preview of the generated server config."""
        if not obj or not obj.pk:
            return mark_safe('<em>Save the server first to see config preview.</em>')
        try:
            from .services.onboarding import generate_server_config
            config = generate_server_config(obj, obj.get_private_key())
            # Mask the private key in preview
            lines = config.split("\n")
            masked = []
            for line in lines:
                if line.strip().startswith("PrivateKey"):
                    masked.append("PrivateKey = [ENCRYPTED — HIDDEN]")
                else:
                    masked.append(line)
            preview = "\n".join(masked)
            return format_html(
                '<pre style="background:#0d1117;color:#c9d1d9;padding:16px;'
                'border-radius:8px;overflow-x:auto;font-family:monospace;'
                'font-size:0.85em;line-height:1.5;max-height:400px;'
                'overflow-y:auto;border:1px solid #30363d;">{}</pre>',
                preview,
            )
        except Exception as e:
            return format_html(
                '<div style="padding:10px;background:#2d1b1b;color:#f88;'
                'border-radius:6px;">Error generating preview: {}</div>',
                str(e),
            )
    config_preview.short_description = "Generated Config"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.private_key_encrypted and obj.private_key_encrypted != "-":
            self.message_user(
                request,
                "✅ Server saved. Keys are auto-generated if missing.",
            )
        else:
            self.message_user(
                request,
                "⚠️ Server saved. Refresh to see generated keys.",
                level="warning",
            )


# ============================================================
# PEER ADMIN
# ============================================================

@admin.register(WireGuardPeer)
class PeerAdmin(admin.ModelAdmin):
    list_display = (
        "name", "email", "allowed_ip", "is_active_badge", "platform_badge",
        "get_server_name", "resend_link", "updated_at",
    )
    list_filter = ("is_active", "platform", "server", "created_at")
    search_fields = ("name", "email", "allowed_ip")
    readonly_fields = (
        "public_key", "private_key_encrypted",
        "created_at", "updated_at", "resend_credentials_button",
        "config_preview",
    )
    actions = ["resend_onboarding_email"]
    fieldsets = (
        ("Basic Info", {
            "fields": ("name", "email", "platform", "server"),
        }),
        ("Network Configuration", {
            "fields": ("allowed_ip", "allowed_ips", "dns", "server_endpoint"),
            "description": mark_safe(
                "Leave <strong>Allowed IP</strong> blank to auto-assign the next "
                "available address from the server's VPN subnet."
            ),
        }),
        ("Keys", {
            "fields": ("public_key", "private_key_encrypted"),
            "classes": ("collapse",),
            "description": "Keys are auto-generated during onboarding. No manual input needed.",
        }),
        ("Client Config Preview", {
            "fields": ("config_preview",),
            "description": "Live preview of the WireGuard config that will be sent to this peer.",
        }),
        ("Configuration", {
            "fields": ("qr_path",),
            "classes": ("collapse",),
        }),
        ("Status", {
            "fields": ("is_active", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
        ("Actions", {
            "fields": ("resend_credentials_button",),
            "description": "Re-send VPN configuration and credentials to this peer.",
        }),
    )

    def get_server_name(self, obj):
        if obj.server:
            return obj.server.name
        server = obj.get_server()
        return f"{server.name} (default)" if server else "No server"
    get_server_name.short_description = "Server"

    def is_active_badge(self, obj):
        if obj.is_active:
            return mark_safe(
                '<span style="background:#198754;color:#fff;padding:3px 10px;'
                'border-radius:12px;font-size:0.8em;font-weight:600;">Active</span>'
            )
        return mark_safe(
            '<span style="background:#dc3545;color:#fff;padding:3px 10px;'
            'border-radius:12px;font-size:0.8em;font-weight:600;">Disabled</span>'
        )
    is_active_badge.short_description = "Status"
    is_active_badge.admin_order_field = "is_active"

    def platform_badge(self, obj):
        icons = {
            "android": "🤖", "ios": "🍎", "windows": "🪟",
            "linux": "🐧", "macos": "💻",
        }
        icon = icons.get(obj.platform, "📱")
        return format_html(
            '<span title="{}">{} {}</span>',
            obj.get_platform_display(), icon, obj.get_platform_display(),
        )
    platform_badge.short_description = "Platform"
    platform_badge.admin_order_field = "platform"

    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing existing peer
            return self.readonly_fields + ("created_at",)
        return self.readonly_fields

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            self.message_user(
                request,
                f"✅ Peer '{obj.name}' created with IP {obj.allowed_ip}.",
            )

    # ----------------------------------------------------------
    # Config preview (change form)
    # ----------------------------------------------------------

    def config_preview(self, obj):
        """Show a live preview of the peer config that will be emailed."""
        if not obj or not obj.pk:
            return mark_safe('<em>Save the peer first to see config preview.</em>')
        if not obj.public_key or obj.public_key.strip() in ('', '-'):
            return mark_safe(
                '<em style="color:#e67e22;">Keys not generated yet — '
                'onboarding has not completed.</em>'
            )
        try:
            from .services.onboarding import generate_peer_config
            config = generate_peer_config(obj)
            # Mask the private key in preview
            lines = config.split("\n")
            masked = []
            for line in lines:
                if line.strip().startswith("PrivateKey"):
                    masked.append("PrivateKey = [ENCRYPTED — HIDDEN]")
                else:
                    masked.append(line)
            preview = "\n".join(masked)
            return format_html(
                '<pre style="background:#0d1117;color:#c9d1d9;padding:16px;'
                'border-radius:8px;overflow-x:auto;font-family:monospace;'
                'font-size:0.85em;line-height:1.5;border:1px solid #30363d;">'
                '{}</pre>',
                preview,
            )
        except Exception as e:
            return format_html(
                '<div style="padding:10px;background:#2d1b1b;color:#f88;'
                'border-radius:6px;">⚠️ Error generating preview: {}</div>',
                str(e),
            )
    config_preview.short_description = "Generated Client Config"

    # ----------------------------------------------------------
    # Per-peer resend button (change form)
    # ----------------------------------------------------------

    def resend_credentials_button(self, obj):
        if not obj or not obj.pk:
            return mark_safe('<em>Save the peer first to enable resending.</em>')
        if not obj.public_key or obj.public_key.strip() in ('', '-'):
            return mark_safe(
                '<em style="color: #e67e22;">Keys not generated yet — '
                'onboarding has not completed.</em>'
            )
        return format_html(
            '<a class="button" href="resend-credentials/" '
            'style="padding:10px 24px;background:#0d6efd;color:#fff;'
            'border-radius:6px;text-decoration:none;font-weight:600;'
            'font-size:0.95em;display:inline-block;">'
            '📧 Resend Credentials</a>'
            '<span style="margin-left:12px;color:#888;font-size:0.85em;">'
            'Sends config + QR code to {}</span>',
            obj.email,
        )
    resend_credentials_button.short_description = "Resend Credentials"

    # ----------------------------------------------------------
    # Per-peer resend link (list view)
    # ----------------------------------------------------------

    def resend_link(self, obj):
        if not obj.public_key or obj.public_key.strip() in ('', '-'):
            return mark_safe('<span style="color:#999;">—</span>')
        return format_html(
            '<a href="{}/resend-credentials/" '
            'style="color:#0d6efd;font-weight:600;text-decoration:none;">'
            '📧 Resend</a>',
            obj.pk,
        )
    resend_link.short_description = "Resend"

    # ----------------------------------------------------------
    # Custom admin URL for per-peer resend
    # ----------------------------------------------------------

    def get_urls(self):
        from django.urls import path
        custom_urls = [
            path(
                '<int:peer_id>/resend-credentials/',
                self.admin_site.admin_view(self.resend_credentials_view),
                name='wireguard_wireguardpeer_resend',
            ),
        ]
        return custom_urls + super().get_urls()

    def resend_credentials_view(self, request, peer_id):
        from django.http import HttpResponseRedirect
        from .tasks import onboard_peer

        try:
            peer = WireGuardPeer.objects.get(id=peer_id)
            onboard_peer.delay(peer.id)
            messages.success(
                request,
                f"📧 Queued credential resend for '{peer.name}' ({peer.email})."
            )
        except WireGuardPeer.DoesNotExist:
            messages.error(request, f"Peer with ID {peer_id} not found.")
        except Exception as e:
            messages.error(request, f"Failed to queue resend: {e}")

        return HttpResponseRedirect("../../")

    # ----------------------------------------------------------
    # Batch action (list view checkbox selection)
    # ----------------------------------------------------------

    def resend_onboarding_email(self, request, queryset):
        """Re-trigger onboarding (regenerate config + send email) for selected peers."""
        from .tasks import onboard_peer
        count = 0
        for peer in queryset:
            try:
                onboard_peer.delay(peer.id)
                count += 1
            except Exception as e:
                self.message_user(
                    request, f"Failed to queue {peer.name}: {e}", level="error"
                )
        if count:
            self.message_user(
                request, f"📧 Queued credential resend for {count} peer(s)."
            )
    resend_onboarding_email.short_description = "📧 Resend configuration email"


# ============================================================
# SMTP SETTINGS ADMIN
# ============================================================

class SMTPSettingsForm(forms.ModelForm):
    password_input = forms.CharField(
        widget=forms.PasswordInput(render_value=False),
        required=False,
        label="SMTP Password",
        help_text=(
            "Enter a new password (e.g., Google App Password) to update it. "
            "Leave blank to keep the currently saved password."
        ),
    )

    class Meta:
        model = SMTPSettings
        fields = ["host", "port", "username", "password_input", "from_email"]

    def clean_host(self):
        host = self.cleaned_data.get("host", "").strip()
        if host == "smtp.google.com":
            raise forms.ValidationError(
                "Invalid SMTP host 'smtp.google.com'. "
                "Did you mean 'smtp.gmail.com'?"
            )
        if not host:
            raise forms.ValidationError("SMTP host cannot be empty.")
        return host

    def save(self, commit=True):
        instance = super().save(commit=False)
        raw_password = self.cleaned_data.get("password_input")
        if raw_password:
            instance.set_password(raw_password)
        if commit:
            instance.save()
        return instance


@admin.register(SMTPSettings)
class SMTPSettingsAdmin(admin.ModelAdmin):
    form = SMTPSettingsForm
    list_display = ("host_display", "port", "username", "from_email")

    def host_display(self, obj):
        if obj.host == "smtp.google.com":
            return format_html(
                '<span style="color:#dc3545;font-weight:600;">'
                '⚠️ {} (incorrect — should be smtp.gmail.com)</span>',
                obj.host,
            )
        return format_html(
            '<span style="font-weight:600;">{}</span>', obj.host
        )
    host_display.short_description = "Host"
    host_display.admin_order_field = "host"
