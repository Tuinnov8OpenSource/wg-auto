import logging
import os
import shutil
import subprocess

from celery import shared_task
from django.conf import settings

from .models import WireGuardPeer, WireGuardServer
from .services.onboarding import onboard, generate_server_config

logger = logging.getLogger(__name__)


from celery.signals import worker_ready

@worker_ready.connect
def on_worker_ready(**kwargs):
    """Start active WireGuard servers when the Celery worker boots."""
    try:
        active_servers = WireGuardServer.objects.filter(is_active=True)
        for server in active_servers:
            logger.info("[WG_BOOT] Synchronizing active server: %s", server.interface)
            sync_wg_config.delay(server.id)
    except Exception as e:
        logger.error("[WG_BOOT] Failed to initialize servers on boot: %s", e)

# ============================================================
# Binary resolution — Docker-aware (no sudo when running root)
# ============================================================

def _find_bin(name: str, fallback: str) -> str:
    """Locate a binary on $PATH, falling back to an absolute path."""
    return shutil.which(name) or fallback


def _is_root() -> bool:
    """Return True when the process is already running as root."""
    return os.getuid() == 0


WG = _find_bin("wg", "/usr/bin/wg")
WG_QUICK = _find_bin("wg-quick", "/usr/bin/wg-quick")
TEE = _find_bin("tee", "/usr/bin/tee")
CHMOD = _find_bin("chmod", "/usr/bin/chmod")
SUDO = _find_bin("sudo", "/usr/bin/sudo")

# When running as root (Docker containers), sudo is not needed
USE_SUDO = not _is_root()


def _cmd(args: list[str]) -> list[str]:
    """Prefix command with sudo if needed."""
    if USE_SUDO:
        return [SUDO, "-n"] + args
    return args


# ============================================================
# Peer Onboarding Task
# ============================================================

@shared_task(bind=True, max_retries=5)
def onboard_peer(self, peer_id: int):
    from .services.onboarding import OnboardingEmailError

    try:
        # Phase 1: Infrastructure setup (idempotent)
        # This runs onboard() which sets up keys, IP, QR, then sends email
        onboard(peer_id)
        logger.info("[ONBOARD] Completed for peer %s", peer_id)
        return {"status": "success", "peer_id": peer_id}

    except WireGuardPeer.DoesNotExist:
        logger.error("[ONBOARD] Peer %s not found — will not retry", peer_id)
        return {"status": "error", "message": "Peer not found"}

    except OnboardingEmailError as e:
        # Infrastructure succeeded but email failed — retry only email
        countdown = min(30 * (2 ** self.request.retries), 300)
        logger.warning(
            "[ONBOARD] Email failed for peer %s (attempt %d/%d), "
            "retrying in %ds: %s",
            peer_id, self.request.retries + 1, self.max_retries,
            countdown, e,
        )
        raise self.retry(exc=e, countdown=countdown)

    except Exception as e:
        logger.exception("[ONBOARD] Infrastructure error for peer %s: %s", peer_id, e)
        raise self.retry(exc=e, countdown=10)


# ============================================================
# Server Configuration Sync Task
# ============================================================

@shared_task(bind=True, max_retries=2)
def sync_wg_config(self, server_id: int):
    try:
        server = WireGuardServer.objects.get(id=server_id)
        private_key = server.get_private_key()
        config_content = generate_server_config(server, private_key)

        config_path = f"/etc/wireguard/{server.interface}.conf"

        # Write config (sudo only when not root)
        proc = subprocess.run(
            _cmd([TEE, config_path]),
            input=config_content,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if proc.returncode != 0:
            raise PermissionError(proc.stderr.strip())

        # Secure permissions
        subprocess.run(
            _cmd([CHMOD, "600", config_path]),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        logger.info("[WG_SYNC] Config written: %s", config_path)

        # Check interface state
        wg_show = subprocess.run(_cmd([WG, "show", server.interface]), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        is_up = (wg_show.returncode == 0)

        # Ensure interface is up if active, or down if inactive
        if server.is_active and not is_up:
            up_proc = subprocess.run(_cmd([WG_QUICK, "up", config_path]), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if up_proc.returncode != 0:
                logger.error("[WG_SYNC] Failed to bring up %s: %s", server.interface, up_proc.stderr.strip())
            else:
                logger.info("[WG_SYNC] Brought up interface %s", server.interface)
        elif not server.is_active and is_up:
            down_proc = subprocess.run(_cmd([WG_QUICK, "down", config_path]), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if down_proc.returncode != 0:
                logger.error("[WG_SYNC] Failed to bring down %s: %s", server.interface, down_proc.stderr.strip())
            else:
                logger.info("[WG_SYNC] Brought down interface %s", server.interface)

        return {"status": "success", "server": server.interface}

    except WireGuardServer.DoesNotExist:
        logger.error("[WG_SYNC] Server %s not found", server_id)
        return {"status": "error", "message": "Server not found"}

    except PermissionError as e:
        logger.error("[WG_SYNC] Permission error: %s", e)
        # Do NOT retry endlessly on sudo failures
        raise

    except Exception as e:
        logger.exception("[WG_SYNC] Error: %s", e)
        raise self.retry(exc=e, countdown=10)


# ============================================================
# Live Peer Injection Task
# ============================================================

@shared_task(bind=True, max_retries=2)
def inject_peer_live(self, peer_id: int):
    try:
        peer = WireGuardPeer.objects.get(id=peer_id)
        server = peer.get_server()

        if not server or not server.is_active:
            return {"status": "skipped", "reason": "No active server"}

        if not peer.public_key or peer.public_key.strip() in ("", "-"):
            logger.warning("[WG_INJECT] Public key missing for %s", peer.name)
            return {"status": "skipped", "reason": "No public key"}

        if peer.is_active:
            cmd = _cmd([
                WG, "set", server.interface,
                "peer", peer.public_key,
                "allowed-ips", f"{peer.allowed_ip}/32",
            ])

            if server.persistent_keepalive:
                cmd += ["persistent-keepalive", str(server.persistent_keepalive)]

            action = "inject"

        else:
            cmd = _cmd([
                WG, "set", server.interface,
                "peer", peer.public_key,
                "remove",
            ])
            action = "remove"

        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if proc.returncode != 0:
            error_msg = proc.stderr.strip()
            if "No such device" in error_msg:
                logger.warning("[WG_INJECT] Interface %s is not up, skipping live injection", server.interface)
                return {"status": "skipped", "reason": "Interface down"}
            raise PermissionError(error_msg)

        logger.info("[WG_INJECT] Peer %s %sed on %s", peer.name, action, server.interface)
        return {"status": "success", "peer": peer.name}

    except WireGuardPeer.DoesNotExist:
        logger.error("[WG_INJECT] Peer %s not found", peer_id)
        return {"status": "error", "message": "Peer not found"}

    except PermissionError as e:
        logger.error("[WG_INJECT] Permission error: %s", e)
        raise

    except Exception as e:
        logger.exception("[WG_INJECT] Error: %s", e)
        raise self.retry(exc=e, countdown=5)


# ============================================================
# Live Peer Removal Task (by public key, for deleted peers)
# ============================================================

@shared_task(bind=True, max_retries=2)
def remove_peer_live(self, public_key: str, interface: str):
    """
    Remove a peer from the live WireGuard interface by public key.
    Used when a peer is deleted (no longer exists in DB).
    """
    try:
        proc = subprocess.run(
            _cmd([
                WG, "set", interface,
                "peer", public_key,
                "remove",
            ]),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if proc.returncode != 0:
            error_msg = proc.stderr.strip()
            if "No such device" in error_msg:
                logger.warning("[WG_REMOVE] Interface %s is not up, skipping live removal", interface)
                return {"status": "skipped", "reason": "Interface down"}
            raise PermissionError(error_msg)

        logger.info("[WG_REMOVE] Peer removed from %s (key: %s...)", interface, public_key[:20])
        return {"status": "success", "interface": interface}

    except PermissionError as e:
        logger.error("[WG_REMOVE] Permission error: %s", e)
        raise

    except Exception as e:
        logger.exception("[WG_REMOVE] Error: %s", e)
        raise self.retry(exc=e, countdown=5)
