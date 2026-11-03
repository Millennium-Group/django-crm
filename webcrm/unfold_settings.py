"""Unfold (admin UI) configuration.

Kept separate from settings.py so the upstream file stays close to the original
and so branding changes are a one-file diff.

Change SITE_HEADER / SITE_TITLE / the logo paths to re-brand. The sidebar is
ordered for a sales rep's day: pipeline first, tasks second, admin last.
"""
from django.templatetags.static import static
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _


def _profile_link(request):
    from django.urls import reverse

    return reverse('site:common_userprofile_change', args=[request.user.id])


def _help_link(request):
    # imported lazily: crm admin modules must not load while settings is imported
    from common.site.crmsite import get_help_url

    return get_help_url(request)


def _help_permission(request):
    from common.site.crmsite import get_help_url

    return bool(get_help_url(request))

UNFOLD = {
    "SITE_TITLE": "Millennium CRM",
    "SITE_HEADER": "Millennium CRM",
    "SITE_SUBHEADER": _("Sales workspace"),
    "SITE_URL": "/",
    "SITE_ICON": {
        "light": lambda request: static("common/django-crm_logo_24px.svg"),
        "dark": lambda request: static("common/django-crm_logo_24px.svg"),
    },
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "SHOW_BACK_BUTTON": True,
    "BORDER_RADIUS": "8px",
    "ACCOUNT": {
        # rendered in the user menu built by unfold/helpers/account_links.html;
        # this is how the old custom header's profile/help links survive the
        # switch, including on pages that extend admin/base.html directly
        "navigation": [
            {"title": _("My profile"), "link": _profile_link},
            {"title": _("Help"), "link": _help_link},
        ],
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "title": _("Pipeline"),
                "separator": True,
                "items": [
                    {
                        "title": _("Deals"),
                        "icon": "trending_up",
                        "link": reverse_lazy("site:crm_deal_changelist"),
                    },
                    {
                        "title": _("Leads"),
                        "icon": "person_add",
                        "link": reverse_lazy("site:crm_lead_changelist"),
                    },
                    {
                        "title": _("Requests"),
                        "icon": "inbox",
                        "link": reverse_lazy("site:crm_request_changelist"),
                    },
                ],
            },
            {
                "title": _("Accounts"),
                "separator": True,
                "items": [
                    {
                        "title": _("Companies"),
                        "icon": "business",
                        "link": reverse_lazy("site:crm_company_changelist"),
                    },
                    {
                        "title": _("Contacts"),
                        "icon": "person",
                        "link": reverse_lazy("site:crm_contact_changelist"),
                    },
                ],
            },
            {
                "title": _("Work"),
                "separator": True,
                "items": [
                    {
                        "title": _("Tasks"),
                        "icon": "checklist",
                        "link": reverse_lazy("site:tasks_task_changelist"),
                    },
                    {
                        "title": _("Projects"),
                        "icon": "folder_open",
                        "link": reverse_lazy("site:tasks_project_changelist"),
                    },
                ],
            },
            {
                "title": _("Insights"),
                "separator": True,
                "items": [
                    {
                        "title": _("Analytics"),
                        "icon": "insights",
                        "link": reverse_lazy("site:analytics_incomestat_changelist"),
                    },
                ],
            },
            {
                "title": _("Administration"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Users"),
                        "icon": "group",
                        "link": reverse_lazy("admin:auth_user_changelist"),
                        "permission": lambda request: request.user.is_superuser,
                    },
                    {
                        "title": _("API tokens"),
                        "icon": "key",
                        "link": reverse_lazy("admin:api_apitoken_changelist"),
                        "permission": lambda request: request.user.is_staff,
                    },
                    {
                        "title": _("Django admin"),
                        "icon": "admin_panel_settings",
                        "link": reverse_lazy("admin:index"),
                        "permission": lambda request: request.user.is_superuser,
                    },
                ],
            },
        ],
    },
}
