#!/bin/sh
# Container entrypoint: wait for the database, migrate, collect static, serve.
#
# Escape hatches:
#   docker compose run --rm app manage setupdata      -> runs manage.py setupdata
#   docker compose run --rm app sh                    -> shell
#   docker compose run --rm app <any command>         -> exec'd as-is
set -eu

if [ "${1:-}" = "manage" ]; then
    shift
    exec python manage.py "$@"
fi
if [ "$#" -gt 0 ]; then
    exec "$@"
fi

DB_HOST="${POSTGRES_HOST:-db}"
DB_PORT="${POSTGRES_PORT:-5432}"

echo "[entrypoint] waiting for postgres at ${DB_HOST}:${DB_PORT} ..."
python - "$DB_HOST" "$DB_PORT" <<'PY'
import socket
import sys
import time

host, port = sys.argv[1], int(sys.argv[2])
deadline = time.time() + 60
while time.time() < deadline:
    try:
        with socket.create_connection((host, port), timeout=2):
            print(f"[entrypoint] postgres is up after {60 - int(deadline - time.time())}s")
            sys.exit(0)
    except OSError:
        time.sleep(1)
print(f"[entrypoint] postgres at {host}:{port} did not come up in 60s", file=sys.stderr)
sys.exit(1)
PY

# App daemon threads (reminder/notification senders) query the database on
# start; keep them off until the schema exists.
export DJANGO_DISABLE_DAEMONS=1
echo "[entrypoint] applying migrations ..."
python manage.py migrate --noinput

echo "[entrypoint] collecting static files ..."
python manage.py collectstatic --noinput --clear
unset DJANGO_DISABLE_DAEMONS

echo "[entrypoint] starting gunicorn ..."
exec gunicorn webcrm.wsgi:application \
    --bind "0.0.0.0:${GUNICORN_PORT:-8000}" \
    --workers "${GUNICORN_WORKERS:-3}" \
    --threads "${GUNICORN_THREADS:-2}" \
    --timeout "${GUNICORN_TIMEOUT:-120}" \
    --access-logfile - \
    --error-logfile -
