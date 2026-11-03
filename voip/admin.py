from django.contrib import admin
from unfold.admin import ModelAdmin as UnfoldModelAdmin  # noqa: E402
from crm.utils.admfilters import ScrollRelatedOnlyFieldListFilter
from voip.models import Connection


class ConnectionAdmin(UnfoldModelAdmin):
    list_display = (
        'callerid', 'provider', 'number', 'type', 'owner', 'active'
    )
    list_filter = (
        'active', 'type',
        ('owner', ScrollRelatedOnlyFieldListFilter)
    )
    fieldsets = (
        (None, {
            'fields': (
                ('provider', 'active'),
                ('number', 'type'),
                'callerid', 'owner'
            )
        }),
    )


admin.site.register(Connection, ConnectionAdmin)
