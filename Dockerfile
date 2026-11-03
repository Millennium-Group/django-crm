# Django-CRM application image (gunicorn + whitenoise behind Caddy).
#
# Build:  docker compose build
# Run:    docker compose up -d
#
# Everything the instance needs at runtime is environment driven — see
# .env.example and webcrm/settings_docker.py.

FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=webcrm.settings_docker

WORKDIR /app

# Dependencies first so a code change does not invalidate the wheel layer.
# Every requirement ships a manylinux wheel (psycopg[binary] bundles libpq), so
# no compiler toolchain is needed in the image.
COPY requirements.txt requirements-prod.txt ./
RUN pip install --no-cache-dir -r requirements-prod.txt

COPY . .

RUN useradd --create-home --uid 10001 --shell /bin/false app \
    && mkdir -p /app/staticfiles /app/media \
    && chown -R app:app /app \
    && chmod +x /app/docker/entrypoint.sh

USER app

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
