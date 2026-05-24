#!/usr/bin/env bash
set -e

# ============================================================
# WireGuard Auto — Docker Entrypoint
# Handles migrations, static files, and application startup
# ============================================================

echo "=== WireGuard Auto — Starting ==="

# Wait for database to be ready
echo "[entrypoint] Waiting for database..."
until python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.db import connection
connection.ensure_connection()
print('Database ready')
" 2>/dev/null; do
    echo "[entrypoint] Database not ready, retrying in 2s..."
    sleep 2
done

# Run migrations
echo "[entrypoint] Running migrations..."
python manage.py migrate --noinput

# Collect static files
echo "[entrypoint] Collecting static files..."
python manage.py collectstatic --noinput --clear 2>/dev/null || true

# Create default superuser if it doesn't exist
echo "[entrypoint] Ensuring default admin user exists..."
python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'wgauto')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@wgauto.local')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'wgauto123')
if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f'Created default superuser: {username}')
else:
    print(f'Superuser {username} already exists, skipping.')
"

# Start gunicorn (default command)
if [ "$#" -eq 0 ]; then
    echo "[entrypoint] Starting Gunicorn..."
    exec gunicorn config.wsgi:application \
        --bind 0.0.0.0:8004 \
        --workers 3 \
        --timeout 120 \
        --max-requests 1000 \
        --max-requests-jitter 50 \
        --access-logfile /app/logs/access.log \
        --error-logfile /app/logs/error.log \
        --log-level info
else
    # Run custom command (e.g., celery worker)
    echo "[entrypoint] Running: $*"
    exec "$@"
fi
