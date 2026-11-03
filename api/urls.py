"""URL wiring for the CRM API.

Mounted at /api/ (not inside i18n_patterns on purpose: API paths stay stable
and language-independent).
"""
from django.urls import path

from .views import api

urlpatterns = [
    path('', api.urls),
]
