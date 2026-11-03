"""django-ninja API for Django-CRM.

Auth
----
* ``Authorization: Bearer crm_<prefix><secret>`` — integration tokens (see
  :class:`api.models.ApiToken`), issued in the admin or via ``POST /api/tokens``.
* Django session — what the browser uses, so ``/api/docs`` works when logged in.

Visibility
----------
Superusers see every record. Everyone else sees records they own or co-own.
Department-wide visibility is what the CRM admin applies; it is intentionally
*not* mirrored here yet (see README.md in this app).
"""
from typing import Optional

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404
from ninja import NinjaAPI, Router
from ninja.pagination import LimitOffsetPagination, paginate
from ninja.security import HttpBearer, django_auth

from .models import ApiToken
from .schemas import (
    CompanyOut,
    ContactOut,
    DealIn,
    DealOut,
    DealPatch,
    HealthOut,
    LeadIn,
    LeadOut,
    LeadPatch,
    MeOut,
    TaskOut,
    TokenCreatedOut,
    TokenIn,
    TokenOut,
)

User = get_user_model()

VERSION = '1.0.0'


class ApiKeyAuth(HttpBearer):
    def authenticate(self, request, token):
        api_token = ApiToken.resolve(token)
        if api_token:
            return api_token.user
        return None


api = NinjaAPI(
    title='Django CRM API',
    version=VERSION,
    description='Leads, deals, companies, contacts and tasks for the sales team.',
    auth=[ApiKeyAuth(), django_auth],
    urls_namespace='api',
)


def _user(request):
    """The authenticated user (token auth leaves request.user anonymous)."""
    auth = getattr(request, 'auth', None)
    if isinstance(auth, User):
        return auth
    return request.user


def _own_qs(model, request, fields=('owner',)):
    qs = model.objects.all()
    user = _user(request)
    if user.is_superuser:
        return qs
    condition = Q(**{f'{fields[0]}': user})
    for extra in fields[1:]:
        condition |= Q(**{extra: user})
    return qs.filter(condition)


def _norm_nulls(model, data):
    """Turn explicit ``None`` into '' for non-null text columns.

    Pydantic emits ``None`` for every optional field the client left out, which
    would otherwise overwrite a model default with SQL NULL.
    """
    from django.db import models
    from django.core.exceptions import FieldDoesNotExist

    for key, value in list(data.items()):
        if value is not None:
            continue
        try:
            field = model._meta.get_field(key)
        except FieldDoesNotExist:
            continue
        if isinstance(field, (models.CharField, models.TextField, models.SlugField))                 and not field.null:
            data[key] = ''
    return data

def _staff(request):
    return _user(request).is_staff


# ------------------------------------------------------------------ meta
@api.get('/health', response=HealthOut, auth=None, tags=['meta'])
def health(request):
    return {'status': 'ok', 'version': VERSION}


@api.get('/me', response=MeOut, tags=['meta'])
def me(request):
    user = _user(request)
    return {
        'id': user.id,
        'username': user.get_username(),
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
    }


# ------------------------------------------------------------------ tokens
@api.get('/tokens', response=list[TokenOut], tags=['meta'])
def list_tokens(request):
    return list(ApiToken.objects.filter(user=_user(request)))


@api.post('/tokens', response={201: TokenCreatedOut}, tags=['meta'])
def create_token(request, payload: TokenIn):
    obj, raw = ApiToken.issue(_user(request), payload.name)
    return 201, {
        'id': obj.id,
        'name': obj.name,
        'prefix': obj.prefix,
        'created_at': obj.created_at,
        'last_used_at': obj.last_used_at,
        'token': raw,
    }


@api.delete('/tokens/{token_id}', response={204: None}, tags=['meta'])
def revoke_token(request, token_id: int):
    ApiToken.objects.filter(pk=token_id, user=_user(request)).delete()
    return 204, None


# ------------------------------------------------------------------ leads
leads = Router(tags=['leads'])


@leads.get('/', response=list[LeadOut])
@paginate(LimitOffsetPagination)
def list_leads(request, q: Optional[str] = None, disqualified: Optional[bool] = None):
    from crm.models import Lead

    qs = _own_qs(Lead, request).order_by('-creation_date')
    if q:
        qs = qs.filter(
            Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(email__icontains=q)
            | Q(company_name__icontains=q)
        )
    if disqualified is not None:
        qs = qs.filter(disqualified=disqualified)
    return qs


@leads.post('/', response={201: LeadOut})
def create_lead(request, payload: LeadIn):
    from crm.models import Lead

    data = payload.model_dump(exclude_none=True)
    data['modified_by'] = _user(request)
    if data.get('owner_id') is None:
        data['owner_id'] = _user(request).id
    lead = Lead.objects.create(**data)
    return 201, lead


@leads.get('/{lead_id}', response=LeadOut)
def get_lead(request, lead_id: int):
    from crm.models import Lead

    return get_object_or_404(_own_qs(Lead, request), pk=lead_id)


@leads.patch('/{lead_id}', response=LeadOut)
def update_lead(request, lead_id: int, payload: LeadPatch):
    from crm.models import Lead

    lead = get_object_or_404(_own_qs(Lead, request), pk=lead_id)
    changes = _norm_nulls(model=type(lead), data=payload.model_dump(exclude_unset=True))
    for field, value in changes.items():
        setattr(lead, field, value)
    lead.modified_by = _user(request)
    lead.save()
    return lead


@leads.delete('/{lead_id}', response={204: None})
def delete_lead(request, lead_id: int):
    from crm.models import Lead

    if not _staff(request):
        from ninja.errors import HttpError

        raise HttpError(403, 'Only staff can delete leads.')
    lead = get_object_or_404(_own_qs(Lead, request), pk=lead_id)
    lead.delete()
    return 204, None


api.add_router('/leads', leads)


# ------------------------------------------------------------------ deals
deals = Router(tags=['deals'])


@deals.get('/', response=list[DealOut])
@paginate(LimitOffsetPagination)
def list_deals(request, q: Optional[str] = None, active: Optional[bool] = None):
    from crm.models import Deal

    qs = _own_qs(Deal, request, fields=('owner', 'co_owner')).order_by('-creation_date')
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(next_step__icontains=q))
    if active is not None:
        qs = qs.filter(active=active)
    return qs


@deals.post('/', response={201: DealOut})
def create_deal(request, payload: DealIn):
    from crm.models import Deal

    data = payload.model_dump(exclude_none=True)
    data['modified_by'] = _user(request)
    if data.get('owner_id') is None:
        data['owner_id'] = _user(request).id
    deal = Deal.objects.create(**data)
    return 201, deal


@deals.get('/{deal_id}', response=DealOut)
def get_deal(request, deal_id: int):
    from crm.models import Deal

    return get_object_or_404(_own_qs(Deal, request, fields=('owner', 'co_owner')), pk=deal_id)


@deals.patch('/{deal_id}', response=DealOut)
def update_deal(request, deal_id: int, payload: DealPatch):
    from crm.models import Deal

    deal = get_object_or_404(_own_qs(Deal, request, fields=('owner', 'co_owner')), pk=deal_id)
    changes = _norm_nulls(model=type(deal), data=payload.model_dump(exclude_unset=True))
    for field, value in changes.items():
        setattr(deal, field, value)
    deal.modified_by = _user(request)
    deal.save()
    return deal


api.add_router('/deals', deals)


# ------------------------------------------------------------------ companies
companies = Router(tags=['companies'])


@companies.get('/', response=list[CompanyOut])
@paginate(LimitOffsetPagination)
def list_companies(request, q: Optional[str] = None):
    from crm.models import Company

    qs = _own_qs(Company, request).order_by('-creation_date')
    if q:
        qs = qs.filter(
            Q(full_name__icontains=q) | Q(email__icontains=q) | Q(website__icontains=q)
        )
    return qs


@companies.get('/{company_id}', response=CompanyOut)
def get_company(request, company_id: int):
    from crm.models import Company

    return get_object_or_404(_own_qs(Company, request), pk=company_id)


api.add_router('/companies', companies)


# ------------------------------------------------------------------ contacts
contacts = Router(tags=['contacts'])


@contacts.get('/', response=list[ContactOut])
@paginate(LimitOffsetPagination)
def list_contacts(request, q: Optional[str] = None):
    from crm.models import Contact

    qs = _own_qs(Contact, request).order_by('-creation_date')
    if q:
        qs = qs.filter(
            Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q)
        )
    return qs


@contacts.get('/{contact_id}', response=ContactOut)
def get_contact(request, contact_id: int):
    from crm.models import Contact

    return get_object_or_404(_own_qs(Contact, request), pk=contact_id)


api.add_router('/contacts', contacts)


# ------------------------------------------------------------------ tasks
tasks = Router(tags=['tasks'])


@tasks.get('/', response=list[TaskOut])
@paginate(LimitOffsetPagination)
def list_tasks(request, q: Optional[str] = None, active: Optional[bool] = None):
    from tasks.models import Task

    qs = _own_qs(Task, request, fields=('owner', 'co_owner')).order_by('-creation_date')
    if q:
        qs = qs.filter(name__icontains=q)
    if active is not None:
        qs = qs.filter(active=active)
    return qs


@tasks.get('/{task_id}', response=TaskOut)
def get_task(request, task_id: int):
    from tasks.models import Task

    return get_object_or_404(_own_qs(Task, request, fields=('owner', 'co_owner')), pk=task_id)


api.add_router('/tasks', tasks)
