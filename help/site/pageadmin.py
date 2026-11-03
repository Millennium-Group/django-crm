from django.contrib import admin
from unfold.admin import ModelAdmin as UnfoldModelAdmin  # noqa: E402

from help.site.paragraphInline import ParagraphInline


class PageAdmin(UnfoldModelAdmin):
    exclude = (
        'app_label',
        'page',
        'main',
        'model',
        'title',
        'language_code',
        'draft'
    )
    inlines = [ParagraphInline]

    # -- ModelAdmin methods -- #

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return True
