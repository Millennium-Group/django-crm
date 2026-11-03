"""API access tokens.

A token is shown to the user exactly once (at creation) and stored as a
SHA-256 digest. The visible prefix is kept in clear so a lookup can happen
before the (constant-time) digest comparison.
"""
import hashlib
import hmac
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

TOKEN_PREFIX = 'crm'
PREFIX_LEN = 8


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


class ApiToken(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='api_tokens',
        verbose_name=_('User'),
    )
    name = models.CharField(
        _('Name'), max_length=64, help_text=_('Where this token is used, e.g. "n8n"')
    )
    prefix = models.CharField(max_length=16, db_index=True, editable=False)
    hashed_key = models.CharField(max_length=64, editable=False)
    is_active = models.BooleanField(_('Active'), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(_('Last used'), null=True, blank=True)

    class Meta:
        verbose_name = _('API token')
        verbose_name_plural = _('API tokens')
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.name} ({self.user})'

    # ---- token lifecycle -------------------------------------------------
    @classmethod
    def issue(cls, user, name: str) -> tuple['ApiToken', str]:
        """Create a token and return (instance, raw_token).

        The raw token is not recoverable afterwards.
        """
        raw_token = f'{TOKEN_PREFIX}_{secrets.token_urlsafe(32)}'
        obj = cls.objects.create(
            user=user,
            name=name,
            prefix=raw_token[:len(TOKEN_PREFIX) + 1 + PREFIX_LEN],
            hashed_key=hash_token(raw_token),
        )
        return obj, raw_token

    @classmethod
    def resolve(cls, raw_token: str) -> 'ApiToken | None':
        """Return the matching active token, or None."""
        if not raw_token or not raw_token.startswith(f'{TOKEN_PREFIX}_'):
            return None
        prefix = raw_token[:len(TOKEN_PREFIX) + 1 + PREFIX_LEN]
        digest = hash_token(raw_token)
        for candidate in cls.objects.select_related('user').filter(
            prefix=prefix, is_active=True
        ):
            if hmac.compare_digest(candidate.hashed_key, digest):
                if not candidate.user.is_active:
                    return None
                cls.objects.filter(pk=candidate.pk).update(last_used_at=timezone.now())
                return candidate
        return None
