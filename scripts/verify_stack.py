"""Smoke verification for the upgraded stack.

Runs against the real (sqlite) dev database with Django's test client, so it
exercises URL routing, the two admin sites, Unfold rendering and the API
without needing a live server or a browser.
"""
import os
import pathlib
import sys

import django

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webcrm.settings')
django.setup()

from django.conf import settings  # noqa: E402

settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver']

from django.contrib.auth.models import User  # noqa: E402
from django.test import Client  # noqa: E402
from django.urls import reverse  # noqa: E402

from crm.models import Deal  # noqa: E402

USERNAME = 'IamSUPER'
PASSWORD = os.environ.get('VERIFY_PASSWORD', '')

results = []


def check(label, ok, detail=''):
    results.append((label, ok, detail))
    print(('PASS ' if ok else 'FAIL ') + label + (f' — {detail}' if detail else ''))


client = Client()

# --- unauthenticated -------------------------------------------------------
r = client.get('/api/health')
check('api: /api/health is public', r.status_code == 200, str(r.status_code))

r = client.get(reverse('api:list_leads'))
check('api: leads require auth', r.status_code == 401, str(r.status_code))

r = client.get(reverse('admin:index'))
check('admin: redirects anonymous user to login', r.status_code == 302, str(r.status_code))

# --- authenticated ---------------------------------------------------------
user = User.objects.get(username=USERNAME)
if PASSWORD:
    logged_in = client.login(username=USERNAME, password=PASSWORD)
else:
    client.force_login(user)
    logged_in = True
check('auth: session established', bool(logged_in))

r = client.get('/api/docs')
check('api: /api/docs renders', r.status_code == 200 and b'swagger' in r.content.lower(),
      f'{r.status_code}')

r = client.get(reverse('api:list_leads'))
check('api: leads OK for authenticated user', r.status_code == 200, str(r.status_code))
if r.status_code == 200:
    payload = r.json()
    check('api: paginated envelope', 'items' in payload and 'count' in payload,
          str(list(payload)[:4]))

r = client.get(reverse('api:list_deals'))
check('api: deals OK', r.status_code == 200, str(r.status_code))

# CRM admin site (namespace "site")
url = reverse('site:crm_deal_changelist')
r = client.get(url)
unfold_marker = b'unfold' in r.content.lower() or b'Millennium CRM' in r.content
check(f'crm admin: deal changelist renders ({url})', r.status_code == 200, str(r.status_code))
check('crm admin: Unfold chrome present', unfold_marker)

deal = Deal.objects.first()
if deal:
    url = reverse('site:crm_deal_change', args=[deal.id])
    r = client.get(url)
    check(f'crm admin: deal change form renders ({url})', r.status_code == 200, str(r.status_code))
    body = r.content.decode('utf-8', 'ignore')
    check('crm admin: Unfold form styling (rounded-default/class hooks)',
          ('rounded-default' in body) or ('dark:bg-base' in body))
    check('crm admin: record id in page title', f'ID{deal.id}' in body)

# Django admin site (namespace "admin")
for name, label in [
    ('admin:index', 'admin index'),
    ('admin:auth_user_changelist', 'admin users'),
    ('admin:api_apitoken_changelist', 'admin API tokens'),
]:
    url = reverse(name)
    r = client.get(url)
    check(f'admin: {label} renders', r.status_code == 200, f'{r.status_code} {url}')

# sidebar links configured in UNFOLD all resolve
from webcrm.unfold_settings import UNFOLD  # noqa: E402

bad = []
for group in UNFOLD['SIDEBAR']['navigation']:
    for item in group['items']:
        link = item['link']
        try:
            str(link)
        except Exception as exc:  # noqa: BLE001
            bad.append(f"{item['title']}: {exc}")
check('unfold: every sidebar link reverses', not bad, '; '.join(bad))

failed = [r for r in results if not r[1]]
print(f'\n{len(results) - len(failed)}/{len(results)} checks passed')
raise SystemExit(1 if failed else 0)
