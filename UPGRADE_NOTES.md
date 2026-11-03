# Fork notes — Django 6.1 + REST API + Unfold admin

Branch: `django-6.1-api-unfold`, based on upstream `b1e9f2e` (v3.1.0 + unreleased fixes).

Baseline before the work: Django 6.0.8, no API, stock Django admin chrome.

## 1. Django 6.1.2

| Change | File | Why |
|---|---|---|
| `Django==6.0.8` → `6.1.2` | `requirements.txt` | current stable (released 2026-10-06) |
| `mysqlclient` moved out of the default requirements | `requirements-mysql.txt` | no Windows wheel — the default install now uses **psycopg 3** for PostgreSQL; MySQL users install the extra file (needs a C toolchain) |
| `psycopg[binary]==3.3.7` added | `requirements.txt` | Postgres driver, prebuilt wheels |
| `InclusionAdminNode` compat shim | `common/templatetags/crm_list.py` | Django 6.1 added a leading `name` argument to `InclusionAdminNode.__init__`; the old call raised `TypeError: missing 1 required positional argument: 'token'`. Shim detects the signature, so 6.0 still works. |

`manage.py check` is clean on 6.1.2.

## 2. REST API (`api/` app, django-ninja 1.7.3)

Mounted at `/api/` (outside `i18n_patterns`, so paths are stable).

| Endpoint | Notes |
|---|---|
| `GET /api/health` | public |
| `GET /api/docs` | OpenAPI UI (session auth) |
| `GET /api/me` | token or session |
| `GET|POST /api/leads/`, `GET|PATCH|DELETE /api/leads/{id}` | paginated envelope `{items, count}` |
| `GET|POST /api/deals/`, `GET|PATCH /api/deals/{id}` | |
| `GET /api/companies/`, `/api/companies/{id}` | read-only for now |
| `GET /api/contacts/`, `/api/contacts/{id}` | read-only for now |
| `GET /api/tasks/`, `/api/tasks/{id}` | read-only for now |
| `GET|POST|DELETE /api/tokens`, `/api/tokens/{id}` | issue/revoke integration tokens |

Auth: `Authorization: Bearer crm_<prefix><secret>` **or** a Django session.
Tokens live in `api.ApiToken`, stored as SHA-256 digests, shown once at creation,
managed in the Django admin (`Administration → API tokens`) or via `POST /api/tokens`.

Visibility: superusers see everything; everyone else sees records they own or
co-own. **Not yet** mirrored: the CRM's department-wide visibility model.

Trailing slashes are canonical (`/api/leads/`); `/api/leads` 301-redirects.

## 3. Admin UI (django-unfold 0.110.1)

* `unfold`, `unfold.contrib.filters`, `unfold.contrib.forms` added ahead of
  `django.contrib.admin`.
* Both admin sites are Unfold sites now: the default `admin.site` (Unfold's own
  `AppConfig.ready` swap) **and** the CRM's `crm_site`
  (`common/site/crmsite.py: BaseSite(UnfoldAdminSite)`). Without the second one,
  the command palette's `{% url "admin:search" %}` resolves to `site:search`
  and raises `NoReverseMatch` on every CRM changelist.
* `webcrm/unfold_settings.py` — branding (`Millennium CRM`), sidebar ordered for
  a sales rep: Pipeline → Accounts → Work → Insights → Administration.
* ~50 `ModelAdmin` / inline classes migrated from `django.contrib.admin` to
  `unfold.admin` by `scripts/migrate_admin_to_unfold.py` (idempotent, skips
  `super(admin.ModelAdmin, self)` calls). Unstyled forms otherwise.
* Templates: `templates/admin/base.html` and `base_site.html` moved to
  `*_legacy_crm.html`; the new `base_site.html` is Unfold-native and keeps three
  CRM behaviours — `A:` admin-title prefix, per-site favicon, and the copyright
  footer required by the licence.
* Circular-import fix: `tasks/constants.py` hosts `COMPLETED_TITLE` so the
  template-tag library no longer imports admin code (Unfold renders a widget at
  import time, which loaded template libraries mid-import).

**Lost:** the inline `ID<n>` badge next to the page heading (Unfold builds that
heading from its own template tag). The record id is now in the browser title
and the URL.

## 4. Run it locally

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements.txt   # Windows
.venv/Scripts/python.exe manage.py migrate
.venv/Scripts/python.exe manage.py setupdata        # countries, groups, departments, demo users
.venv/Scripts/python.exe manage.py runserver
```

URLs: CRM `/en/123/`, admin `/en/456-admin/`, API `/api/`, docs `/api/docs`.

## 5. Containers (docker compose)

Three services, one image:

| Service | Image | Role |
|---|---|---|
| `db` | `postgres:17-alpine` | database, named volume `pgdata` |
| `app` | built from `Dockerfile` | gunicorn (3 workers x 2 threads) + whitenoise, runs migrate + collectstatic on start |
| `web` | `caddy:2-alpine` | reverse proxy, serves `/media/*` from the shared volume, adds security headers |

* `webcrm/settings_docker.py` — env-driven settings (`DJANGO_SETTINGS_MODULE`),
  fails fast if `DJANGO_SECRET_KEY` is missing. Postgres only, no SQLite.
* `.env.example` → copy to `.env`; secrets are generated per deployment.
* Non-root container user (uid 10001); `media` is a named volume owned by it.
* `DJANGO_DISABLE_DAEMONS=1` is set for the migrate/collectstatic phase only —
  the reminder/notification threads query the DB at import time and otherwise
  traceback on a fresh volume. Flag honoured in `common/apps.py`.
* `.gitattributes` forces LF for `*.sh`, `Dockerfile`, `docker/Caddyfile`: a
  CRLF shebang fails inside Linux with `exec ...: no such file or directory`.

```bash
cp .env.example .env          # then set DJANGO_SECRET_KEY + POSTGRES_PASSWORD
docker compose build
docker compose up -d
docker compose run --rm app manage setupdata     # first-time seed
```

Published port defaults to 8080 (`CRM_HTTP_PORT`). TLS: point
`CRM_SITE_ADDRESS` at a DNS name (Caddy gets a certificate) or uncomment
`tls internal` in `docker/Caddyfile` for a private CA.

Measured footprint on this workstation: app 335 MiB, db 36 MiB, caddy 14 MiB.

## 6. Verification

* `manage.py check` — clean.
* Compose stack on a fresh volume: health 200, API 401 without token / 200 with,
  POST lead 201 + read back, static 362 KB served by whitenoise, media 200 via
  Caddy, login page 200, **0 tracebacks** in the app log, data survives restart.
* `python scripts/verify_stack.py` — 17/17 checks: API auth/CRUD, docs page,
  both admin sites, changelist + change form rendering, Unfold chrome present,
  every sidebar link reverses.
* `manage.py test tests/ --noinput` — **OK (skipped=4)**, 389 passed, exit 0 on
  Django 6.1.2 + Unfold. Baseline on the untouched tree (Django 6.0.8, no API,
  stock admin) was also **393 tests, OK (skipped=4)** — same test count, same
  result, so the upgrade introduced no regressions.
* Known flake: `tests.crm.test_import_export` intermittently raises
  `sqlite3.OperationalError: database table is locked` (an app daemon thread
  writing while the import runs). Passes on re-run; use PostgreSQL for CI.

## 7. Not done yet

* Department-level visibility in the API.
* Write endpoints for companies/contacts/tasks.
* No upstream PR by design: this branch is Millennium-internal (branding, the
  fork-only API app registration, the test normalization for it).
