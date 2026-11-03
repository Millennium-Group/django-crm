from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from .models import ApiToken


@admin.register(ApiToken)
class ApiTokenAdmin(ModelAdmin):
    list_display = ('name', 'user', 'prefix', 'is_active', 'created_at', 'last_used_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'prefix', 'user__username', 'user__email')
    readonly_fields = ('prefix', 'hashed_key', 'created_at', 'last_used_at')
    actions = ('deactivate_tokens',)

    @admin.action(description=_('Deactivate selected tokens'))
    def deactivate_tokens(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, _('%s token(s) deactivated.') % updated)
