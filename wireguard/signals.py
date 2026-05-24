# wireguard/signals.py
import logging
from django.db.models.signals import post_save, pre_delete, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import WireGuardPeer, WireGuardServer, SMTPSettings
from .constants import SMTP_SETTINGS_CACHE_KEY, WG_ACTIVE_PEERS_CACHE_KEY, WG_SERVER_CACHE_KEY

logger = logging.getLogger(__name__)

# ============================================================
# PEER SIGNALS
# ============================================================

@receiver(post_save, sender=WireGuardPeer)
def trigger_onboarding(sender, instance: WireGuardPeer, created, **kwargs):
    """
    Trigger onboarding asynchronously for NEW peers only.
    Internal saves during onboarding (update_fields) are ignored.
    """
    if not created:
        return

    # Skip if this is an internal save with update_fields (shouldn't happen on create, but be safe)
    if kwargs.get("update_fields") is not None:
        return

    from .tasks import onboard_peer
    from django.db import transaction
    try:
        transaction.on_commit(lambda: onboard_peer.delay(instance.id))
        logger.info("Queued onboarding task for peer %s on commit", instance.name)
    except Exception as e:
        logger.exception("Failed to queue onboarding for peer %s: %s", instance.name, e)


@receiver(post_save, sender=WireGuardPeer)
def trigger_peer_injection(sender, instance: WireGuardPeer, created, **kwargs):
    """
    Inject peer into live WireGuard interface on updates only.
    Skips injection during onboarding infrastructure saves (update_fields).
    """
    if created:
        # Skip injection for new peers; onboarding will handle it
        logger.info("New peer %s created - injection will occur after onboarding", instance.name)
        return

    # During onboarding, save() is called with update_fields for specific fields.
    # These are internal state changes, NOT admin/user edits that need live injection.
    update_fields = kwargs.get("update_fields")
    if update_fields is not None:
        onboarding_fields = {"server", "private_key_encrypted", "public_key", "qr_path"}
        if set(update_fields).issubset(onboarding_fields):
            logger.debug(
                "Skipping peer injection for %s — onboarding save (fields: %s)",
                instance.name, update_fields,
            )
            return

    from .tasks import inject_peer_live
    from django.db import transaction
    try:
        transaction.on_commit(lambda: inject_peer_live.delay(instance.id))
        logger.info("Queued peer injection task for %s on commit", instance.name)
    except Exception as e:
        logger.exception("Failed to queue peer injection for %s: %s", instance.name, e)


@receiver(pre_delete, sender=WireGuardPeer)
def trigger_peer_removal(sender, instance: WireGuardPeer, **kwargs):
    """
    When a peer is about to be deleted, remove it from the live interface.
    Uses pre_delete so we can still read the instance data before it's gone.
    """
    if not instance.public_key or instance.public_key.strip() in ('', '-'):
        return

    server = instance.get_server()
    if not server:
        return

    from .tasks import remove_peer_live
    try:
        remove_peer_live.delay(
            public_key=instance.public_key,
            interface=server.interface,
        )
        logger.info("Queued peer removal task for %s", instance.name)
    except Exception as e:
        logger.exception("Failed to queue peer removal for %s: %s", instance.name, e)


# ============================================================
# SERVER SIGNALS
# ============================================================

@receiver(post_save, sender=WireGuardServer)
def invalidate_server_cache(sender, instance: WireGuardServer, **kwargs):
    """
    Invalidate cache when server configuration changes.
    """
    try:
        cache.delete(WG_SERVER_CACHE_KEY)
        cache.delete(WG_ACTIVE_PEERS_CACHE_KEY)
        logger.info("Invalidated server and active peers cache for server %s", instance.name)
    except Exception as e:
        logger.warning("Could not invalidate server cache: %s", e)


@receiver(post_save, sender=WireGuardServer)
def sync_wg_config_on_save(sender, instance: WireGuardServer, **kwargs):
    """
    Regenerate wg0.conf asynchronously when server config changes.
    """
    from .tasks import sync_wg_config
    from django.db import transaction
    try:
        transaction.on_commit(lambda: sync_wg_config.delay(instance.id))
        logger.info("Queued WireGuard config sync for server %s on commit", instance.name)
    except Exception as e:
        logger.exception("Failed to queue config sync for server %s: %s", instance.name, e)


@receiver(post_delete, sender=WireGuardServer)
def invalidate_server_cache_on_delete(sender, instance: WireGuardServer, **kwargs):
    """
    Invalidate cache when server is deleted.
    """
    try:
        cache.delete(WG_SERVER_CACHE_KEY)
        cache.delete(WG_ACTIVE_PEERS_CACHE_KEY)
        logger.info("Invalidated server cache for deleted server %s", instance.name)
    except Exception as e:
        logger.warning("Could not invalidate server cache on delete: %s", e)


# ============================================================
# SMTP SETTINGS CACHE
# ============================================================

@receiver(post_save, sender=SMTPSettings)
@receiver(post_delete, sender=SMTPSettings)
def invalidate_smtp_cache(sender, instance, **kwargs):
    """
    Clear cached SMTP settings whenever they are changed.
    """
    try:
        cache.delete(SMTP_SETTINGS_CACHE_KEY)
        logger.info("SMTP settings cache cleared")
    except Exception as e:
        logger.warning("Could not clear SMTP settings cache: %s", e)
