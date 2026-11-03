from django.contrib import admin
from unfold.admin import ModelAdmin as UnfoldModelAdmin  # noqa: E402


class TagAdmin(UnfoldModelAdmin):
    list_display = ('name', 'for_content')
    fields = ('for_content', 'name')
    radio_fields = {'for_content': admin.VERTICAL}

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['for_content'].empty_label = None
        return form
