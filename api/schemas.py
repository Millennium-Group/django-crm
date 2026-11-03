"""Pydantic schemas for the Django-CRM API.

Deliberately explicit rather than generated from models: the sales API surface
should not silently grow every time a column is added, and FK fields are
returned as plain ids so clients (n8n, the rep's dashboard, AI agents) do not
need to understand Django relations.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from ninja import Schema


class HealthOut(Schema):
    status: str
    version: str


class MeOut(Schema):
    id: int
    username: str
    email: str
    first_name: str
    last_name: str
    is_staff: bool
    is_superuser: bool


# ---------------------------------------------------------------- leads
class LeadOut(Schema):
    id: int
    creation_date: Optional[datetime] = None
    update_date: Optional[datetime] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    company_name: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    disqualified: Optional[bool] = None
    lead_source_id: Optional[int] = None
    owner_id: Optional[int] = None
    company_id: Optional[int] = None
    contact_id: Optional[int] = None
    country_id: Optional[int] = None
    city_name: Optional[str] = None


class LeadIn(Schema):
    first_name: str
    email: str
    last_name: Optional[str] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    company_name: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    disqualified: bool = False
    lead_source_id: Optional[int] = None
    owner_id: Optional[int] = None
    country_id: Optional[int] = None
    city_name: Optional[str] = None


class LeadPatch(Schema):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    company_name: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    disqualified: Optional[bool] = None
    lead_source_id: Optional[int] = None
    owner_id: Optional[int] = None
    country_id: Optional[int] = None
    city_name: Optional[str] = None


# ---------------------------------------------------------------- deals
class DealOut(Schema):
    id: int
    creation_date: Optional[datetime] = None
    update_date: Optional[datetime] = None
    name: Optional[str] = None
    amount: Optional[Decimal] = None
    currency_id: Optional[int] = None
    stage_id: Optional[int] = None
    probability: Optional[int] = None
    next_step: Optional[str] = None
    next_step_date: Optional[date] = None
    closing_date: Optional[date] = None
    description: Optional[str] = None
    active: Optional[bool] = None
    relevant: Optional[bool] = None
    important: Optional[bool] = None
    ticket: Optional[str] = None
    owner_id: Optional[int] = None
    co_owner_id: Optional[int] = None
    company_id: Optional[int] = None
    contact_id: Optional[int] = None
    lead_id: Optional[int] = None
    request_id: Optional[int] = None


class DealIn(Schema):
    name: str
    next_step: str
    next_step_date: date
    amount: Optional[Decimal] = None
    currency_id: Optional[int] = None
    stage_id: Optional[int] = None
    probability: Optional[int] = None
    closing_date: Optional[date] = None
    description: Optional[str] = None
    active: bool = True
    relevant: bool = True
    important: bool = False
    owner_id: Optional[int] = None
    co_owner_id: Optional[int] = None
    company_id: Optional[int] = None
    contact_id: Optional[int] = None
    lead_id: Optional[int] = None
    request_id: Optional[int] = None


class DealPatch(Schema):
    name: Optional[str] = None
    amount: Optional[Decimal] = None
    currency_id: Optional[int] = None
    stage_id: Optional[int] = None
    probability: Optional[int] = None
    next_step: Optional[str] = None
    next_step_date: Optional[date] = None
    closing_date: Optional[date] = None
    description: Optional[str] = None
    active: Optional[bool] = None
    relevant: Optional[bool] = None
    important: Optional[bool] = None
    owner_id: Optional[int] = None
    co_owner_id: Optional[int] = None
    company_id: Optional[int] = None
    contact_id: Optional[int] = None


# ---------------------------------------------------------------- companies
class CompanyOut(Schema):
    id: int
    creation_date: Optional[datetime] = None
    full_name: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    active: Optional[bool] = None
    description: Optional[str] = None
    registration_number: Optional[str] = None
    owner_id: Optional[int] = None
    country_id: Optional[int] = None
    city_name: Optional[str] = None


# ---------------------------------------------------------------- contacts
class ContactOut(Schema):
    id: int
    creation_date: Optional[datetime] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    owner_id: Optional[int] = None
    company_id: Optional[int] = None
    country_id: Optional[int] = None
    city_name: Optional[str] = None


# ---------------------------------------------------------------- tasks
class TaskOut(Schema):
    id: int
    creation_date: Optional[datetime] = None
    name: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    start_date: Optional[datetime] = None
    closing_date: Optional[datetime] = None
    priority: Optional[str] = None
    active: Optional[bool] = None
    next_step: Optional[str] = None
    next_step_date: Optional[date] = None
    owner_id: Optional[int] = None
    co_owner_id: Optional[int] = None
    project_id: Optional[int] = None
    stage_id: Optional[int] = None


# ---------------------------------------------------------------- tokens
class TokenIn(Schema):
    name: str


class TokenOut(Schema):
    id: int
    name: str
    prefix: str
    created_at: datetime
    last_used_at: Optional[datetime] = None


class TokenCreatedOut(TokenOut):
    token: str
