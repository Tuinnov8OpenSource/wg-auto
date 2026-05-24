import os
import logging
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# ── BASE DIR & ENV ────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

dotenv_path = BASE_DIR / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path)
else:
    # Also check parent directory
    alt_dotenv = BASE_DIR.parent / ".env"
    if alt_dotenv.exists():
        load_dotenv(alt_dotenv)

# ── DEBUG (must be defined before any reference) ─────────────────────────────
_debug_value = os.environ.get("DEBUG", "0").lower()
if _debug_value in ("true", "1", "yes", "on"):
    DEBUG = True
elif _debug_value in ("false", "0", "no", "off"):
    DEBUG = False
else:
    try:
        DEBUG = bool(int(_debug_value))
    except ValueError:
        DEBUG = False

# ── SECURITY ──────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("SECRET_KEY") or os.environ.get("DJANGO_SECRET_KEY", "dev-secret-key")

# Warn if using a weak or placeholder SECRET_KEY in non-development environments
if SECRET_KEY in ("changeme", "dev-secret-key", "devkey1234567890") and not DEBUG:
    import warnings
    warnings.warn(
        "Using weak SECRET_KEY in production! "
        "Set DJANGO_SECRET_KEY environment variable to a strong random value.",
        RuntimeWarning,
    )

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if h.strip()
]

# ── APPLICATIONS ─────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_celery_beat",
    "wireguard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"

# ── DATABASE ─────────────────────────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DATABASE_NAME", os.environ.get("POSTGRES_DB", "wg_auto_db")),
        "USER": os.environ.get("DATABASE_USER", os.environ.get("POSTGRES_USER", "postgres")),
        "PASSWORD": os.environ.get("DATABASE_PASSWORD", os.environ.get("POSTGRES_PASSWORD", "postgres")),
        "HOST": os.environ.get("DATABASE_HOST", os.environ.get("POSTGRES_HOST", "127.0.0.1")),
        "PORT": int(os.environ.get("DATABASE_PORT", os.environ.get("POSTGRES_PORT", 5432))),
        "CONN_MAX_AGE": 600,
        "OPTIONS": {
            "connect_timeout": 10,
        },
    }
}

# ── REDIS / CACHES ───────────────────────────────────────────────────────────
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

REDIS_CACHE_URL = os.environ.get("REDIS_CACHE_URL", CELERY_BROKER_URL.replace("/0", "/1"))

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_CACHE_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

# ── ENCRYPTION / WIREGUARD ────────────────────────────────────────────────────
# ENCRYPTION_KEY must be a valid Fernet key (32 url-safe base64-encoded bytes)
# Generate one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
_encryption_key_value = os.environ.get("ENCRYPTION_KEY")

if _encryption_key_value:
    ENCRYPTION_KEY = _encryption_key_value.encode() if isinstance(_encryption_key_value, str) else _encryption_key_value
else:
    # Generate a default key if not provided (for development only)
    from cryptography.fernet import Fernet
    ENCRYPTION_KEY = Fernet.generate_key()
    if not DEBUG:
        import warnings
        warnings.warn(
            "ENCRYPTION_KEY not set in production! Generated a temporary key. "
            "Set ENCRYPTION_KEY in .env with a persistent Fernet key.",
            RuntimeWarning,
        )

WIREGUARD_INTERFACE = os.environ.get("WIREGUARD_INTERFACE", "wg0")
WIREGUARD_ENDPOINT = os.environ.get("WIREGUARD_ENDPOINT", "127.0.0.1:51820")

# ── PASSWORD VALIDATORS ──────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ── INTERNATIONALIZATION ─────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── STATIC FILES ─────────────────────────────────────────────────────────────
STATIC_URL = "static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
os.makedirs(STATIC_ROOT, exist_ok=True)

STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]
os.makedirs(STATICFILES_DIRS[0], exist_ok=True)

MEDIA_URL = "media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")
os.makedirs(MEDIA_ROOT, exist_ok=True)

# ── CSRF TRUSTED ORIGINS ────────────────────────────────────────────────────
_csrf_origins = os.environ.get("CSRF_TRUSTED_ORIGINS", "")
if _csrf_origins:
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_origins.split(",") if o.strip()]
else:
    CSRF_TRUSTED_ORIGINS = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:8004",
        "http://127.0.0.1:8004",
    ]

# ── PRODUCTION SECURITY HEADERS ─────────────────────────────────────────────
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = True
    SESSION_COOKIE_AGE = 3600  # 1 hour
    SESSION_EXPIRE_AT_BROWSER_CLOSE = True

    # Uncomment when behind HTTPS reverse proxy:
    # SECURE_SSL_REDIRECT = True
    # SECURE_HSTS_SECONDS = 31536000
    # SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    # SECURE_HSTS_PRELOAD = True
    # SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ── LOGGING ──────────────────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": os.path.join(BASE_DIR, "logs", "django.log"),
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "wireguard": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# Create logs directory
os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)

# ── JAZZMIN CONFIGURATION ───────────────────────────────────────────────────
JAZZMIN_SETTINGS = {
    "site_title": "WG Auto Admin",
    "site_header": "WireGuard Auto",
    "site_brand": "WG Auto",
    "site_logo": "img/logo.webp",
    "login_logo": "img/logo.webp",
    "welcome_sign": "WireGuard Automation — Secure Access",
    "copyright": "Tuinnov8 — 2026",

    "search_model": ["wireguard.WireGuardPeer"],

    "topmenu_links": [
        {"name": "Dashboard", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "Peers", "url": "admin:wireguard_wireguardpeer_changelist"},
        {"name": "Servers", "url": "admin:wireguard_wireguardserver_changelist"},
    ],

    "show_sidebar": True,
    "navigation_expanded": True,
    "order_with_respect_to": [
        "wireguard",
        "wireguard.wireguardserver",
        "wireguard.wireguardpeer",
        "wireguard.smtpsettings",
        "auth",
        "django_celery_beat",
    ],

    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user-shield",
        "auth.group": "fas fa-users",
        "wireguard.smtpsettings": "fas fa-envelope-open-text",
        "wireguard.wireguardpeer": "fas fa-user-lock",
        "wireguard.wireguardserver": "fas fa-network-wired",
    },

    "default_icon_parents": "fas fa-folder",
    "default_icon_children": "fas fa-circle",

    "custom_css": None,
    "custom_js": None,
    "use_google_fonts_cdn": True,
    "show_ui_builder": False,
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": True,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-dark",
    "accent": "accent-info",
    "navbar": "navbar-dark",
    "no_navbar_border": True,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-info",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "darkly",
    "dark_mode_theme": "darkly",
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-outline-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
    "actions_sticky_top": True,
}

# No Grappelli Config
