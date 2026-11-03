"""Populate the database with plausible demo data for exploration.

    python manage.py seed_demo           # refuse if CRM data already exists
    python manage.py seed_demo --reset   # wipe CRM/task objects first

Deterministic: same seed -> same data, so screenshots stay comparable between
runs. Everything is owned by the sales manager plus three generated reps so the
permissions/department filters have something to filter.
"""
import datetime as dt
import random
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from common.models import Department
from crm.models import (
    Company,
    Contact,
    Country,
    CrmEmail,
    Currency,
    Deal,
    Industry,
    Lead,
    LeadSource,
    Payment,
    Product,
    Request,
    Stage,
)
from tasks.models import Project, ProjectStage, Task, TaskStage

SEED = 20261103
DEMO_PASSWORD = 'DemoPass123!'

FIRST_NAMES = [
    'Dana', 'Priya', 'Marcus', 'Elena', 'Tobias', 'Nadia', 'Owen', 'Sofia',
    'Grant', 'Yuki', 'Andre', 'Bea', 'Caleb', 'Divya', 'Emeka', 'Freya',
    'Hector', 'Imani', 'Jonas', 'Kira', 'Liam', 'Maya', 'Nils', 'Olivia',
    'Pablo', 'Quinn', 'Rosa', 'Samir', 'Tara', 'Umar', 'Vera', 'Wes',
]
LAST_NAMES = [
    'Whitfield', 'Raman', 'Delgado', 'Kovac', 'Brandt', 'Haddad', 'Mercer',
    'Lindqvist', 'Okafor', 'Tanaka', 'Moreau', 'Novak', 'Pierce', 'Nair',
    'Adeyemi', 'Larsen', 'Vega', 'Bennett', 'Fischer', 'Ahmed', 'Doyle',
    'Ortiz', 'Halvorsen', 'Reid', 'Castro', 'Sullivan', 'Marchetti',
]
COMPANY_STEMS = [
    ('Northfield', 'Dental'), ('Loveland', 'Machine Works'), ('Cascade', 'Roofing'),
    ('Front Range', 'Logistics'), ('Big Thompson', 'Electric'), ('Thompson Valley',
    'Dental'), ('Alpine', 'Physio'), ('Sterling', 'Fabrication'),
    ('Boulder Creek', 'Veterinary'), ('Poudre', 'Brewing'), ('Estes', 'Outfitters'),
    ('Horsetooth', 'Property'), ('Centennial', 'Orthodontics'), ('Glacier', 'HVAC'),
    ('Rocky Mountain', 'Imaging'), ('Silver Creek', 'Dental'), ('Summit', 'Law'),
    ('Trailhead', 'Fitness'), ('Windsor', 'Autobody'), ('Berthoud', 'Bakery'),
    ('Greeley', 'Signs'), ('Meadow', 'Landscaping'), ('Sunrise', 'Pediatrics'),
    ('Pioneer', 'Plumbing'), ('Coyote', 'Catering'), ('Aspen', 'Wealth'),
    ('Basalt', 'Clinic'), ('Copper', 'Studio'), ('Denver', 'Courier'),
    ('Flatirons', 'Optometry'), ('Granite', 'Countertops'), ('Hayden', 'Tooling'),
]
CITIES = [
    ('Loveland', 'CO'), ('Fort Collins', 'CO'), ('Greeley', 'CO'), ('Longmont', 'CO'),
    ('Boulder', 'CO'), ('Windsor', 'CO'), ('Berthoud', 'CO'), ('Johnstown', 'CO'),
    ('Estes Park', 'CO'), ('Denver', 'CO'),
]
INDUSTRIES_FALLBACK = ['healthcare', 'construction', 'legal', 'retail', 'manufacturing']
REQUEST_SUBJECTS = [
    'wants a quote for managed IT', 'asked about onboarding timeline',
    'reported a broken backup job', 'needs new workstations quoted',
    'requested a security review', 'asked for VoIP pricing',
    'wants to add two more seats', 'reported slow VPN',
    'asked about MFA rollout', 'wants a network refresh proposal',
]
LEAD_NOTES = [
    'Inbound web form, 12 staff, currently with a break-fix provider.',
    'Referred by their accountant. Wants a fixed monthly number.',
    'Met at the Loveland chamber event, follow up next week.',
    'Ringing the phone line about a ransomware scare.',
    'Evaluating three MSPs, decision expected this quarter.',
]
DEAL_STEPS = [
    'Send the SOW', 'Book a discovery call', 'Follow up on the proposal',
    'Chase the signed agreement', 'Schedule the onboarding kickoff',
    'Confirm the seat count', 'Send references', 'Review the security findings',
]
TASK_NAMES = [
    'Run onboarding checklist', 'Collect signed SOW', 'Audit backup coverage',
    'Rotate the admin credentials', 'Document the network', 'Order the firewall',
    'Schedule the migration window', 'Review the MFA rollout',
    'Follow up on the invoice', 'Prepare the quarterly review',
]


class Command(BaseCommand):
    help = 'Create demo CRM data for exploration.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='delete existing CRM/task data first')
        parser.add_argument('--companies', type=int, default=60)
        parser.add_argument('--leads', type=int, default=65)
        parser.add_argument('--deals', type=int, default=75)
        parser.add_argument('--requests', type=int, default=45)
        parser.add_argument('--tasks', type=int, default=65)

    @transaction.atomic
    def handle(self, *args, **options):
        rnd = random.Random(SEED)

        if Deal.objects.exists() and not options['reset']:
            raise CommandError('CRM data already present. Re-run with --reset to wipe and reseed.')

        if options['reset']:
            self.stdout.write('deleting existing CRM/task data ...')
            for model in (Payment, CrmEmail, Deal, Request, Lead, Contact, Company,
                          Task, Project, Product):
                deleted, _ = model.objects.all().delete()
                self.stdout.write(f'  {model.__name__}: {deleted}')

        departments = list(Department.objects.all())
        if not departments:
            raise CommandError('No departments found — run `manage.py setupdata` first.')
        global_sales = next((d for d in departments if 'global' in d.name.lower()), departments[0])
        local_sales = next((d for d in departments if 'local' in d.name.lower()), global_sales)

        reps = self._ensure_reps(global_sales, local_sales)
        manager = User.objects.filter(username='IamGlobalSALES').first() or reps[0]

        # The CRM only lets a user open records that belong to their own
        # department (clarify_permission), so owners must match the record's
        # department or the seeded data is full of unopenable rows.
        def _dept_users(dept, extra=()):
            names = [u.username for u in dept.user_set.all()]
            users = list(User.objects.filter(username__in=names))
            users += [u for u in extra if u not in users]
            return users or [manager]

        owners_by_dept = {
            # membership comes from the department group; do not add reps here
            # or they end up owning records in a department they cannot open
            global_sales.id: _dept_users(global_sales, [manager]),
            local_sales.id: _dept_users(local_sales),
        }
        owners = list({u.id: u for u in owners_by_dept[global_sales.id] + owners_by_dept[local_sales.id]}.values())

        def owner_for(dept):
            return rnd.choice(owners_by_dept.get(dept.id, owners))

        usd = Currency.objects.filter(name='USD').first() or Currency.objects.first()
        countries = list(Country.objects.all()[:80])
        industries = list(Industry.objects.all())
        lead_sources = list(LeadSource.objects.all())
        task_stages = list(TaskStage.objects.all())
        project_stages = list(ProjectStage.objects.all())

        def contact_person():
            return rnd.choice(FIRST_NAMES), rnd.choice(LAST_NAMES)

        def slug(text):
            return ''.join(c if c.isalnum() else '-' for c in text.lower()).strip('-')

        # ---- companies ----------------------------------------------------
        companies = []
        used_names = set()
        candidates = [f'{stem} {kind}' for stem, kind in COMPANY_STEMS]
        # pad with variants so --companies can exceed the hand-written list
        while len(candidates) < options['companies']:
            stem, kind = rnd.choice(COMPANY_STEMS)
            suffix = rnd.choice([' Group', ' Partners', ' Holdings', ' West',
                                 ' East', ' North', ' II', ' & Sons', ' Services'])
            candidates.append(f'{stem}{suffix}')

        for name in candidates:
            if len(companies) >= options['companies']:
                break
            if name in used_names:
                continue
            used_names.add(name)
            city, _state = rnd.choice(CITIES)
            dept = global_sales if rnd.random() < 0.6 else local_sales
            company = Company.objects.create(
                full_name=name,
                email=f'info@{slug(name)}.example',
                website=f'https://{slug(name)}.example',
                phone=f'970-555-{rnd.randint(1000, 9999)}',
                city_name=city,
                country=rnd.choice(countries) if countries else None,
                description=f'{name} in {city}. {rnd.randint(3, 90)} staff.',
                owner=owner_for(dept),
                department=dept,
                active=True,
                lead_source=rnd.choice(lead_sources) if lead_sources else None,
            )
            if industries:
                company.industry.add(rnd.choice(industries))
            companies.append(company)

        # ---- contacts -----------------------------------------------------
        contacts = []
        for company in companies:
            for _ in range(rnd.randint(1, 3)):
                first, last = contact_person()
                contacts.append(Contact.objects.create(
                    first_name=first,
                    last_name=last,
                    email=f'{first.lower()}.{last.lower()}@{slug(company.full_name)}.example',
                    title=rnd.choice(['Owner', 'Office Manager', 'IT Coordinator', 'CFO', 'Practice Manager']),
                    phone=f'970-555-{rnd.randint(1000, 9999)}',
                    company=company,
                    city_name=company.city_name,
                    country=company.country,
                    owner=company.owner,
                    department=company.department,
                    description='Primary contact for the account.',
                ))

        # ---- leads --------------------------------------------------------
        leads = []
        for i in range(options['leads']):
            first, last = contact_person()
            company_name = f'{rnd.choice(COMPANY_STEMS)[0]} {rnd.choice(COMPANY_STEMS)[1]} #{rnd.randint(2, 9)}'
            lead_dept = global_sales if rnd.random() < 0.65 else local_sales
            leads.append(Lead.objects.create(
                first_name=first,
                last_name=last,
                email=f'{first.lower()}.{last.lower()}{i}@prospect.example',
                company_name=company_name,
                phone=f'970-555-{rnd.randint(1000, 9999)}',
                website=f'https://{slug(company_name)}.example',
                description=rnd.choice(LEAD_NOTES),
                lead_source=rnd.choice(lead_sources) if lead_sources else None,
                owner=owner_for(lead_dept),
                department=lead_dept,
                disqualified=rnd.random() < 0.18,
                country=rnd.choice(countries) if countries else None,
                city_name=rnd.choice(CITIES)[0],
            ))

        # ---- deals --------------------------------------------------------
        deals = []
        for i in range(options['deals']):
            company = rnd.choice(companies)
            contact = next((c for c in contacts if c.company_id == company.id), None)
            stages = list(Stage.objects.filter(department=company.department)) or list(Stage.objects.all())
            stages.sort(key=lambda s: (s.index_number or 0))
            stage = stages[min(len(stages) - 1, int(rnd.triangular(0, len(stages) - 1, 1)))]
            won_stage = next((s for s in stages if getattr(s, 'success_stage', False)), None)
            if won_stage is not None and rnd.random() < 0.18:
                stage = won_stage
            success = bool(getattr(stage, 'success_stage', False))
            created = dt.date(2026, 1, 1) + dt.timedelta(days=rnd.randint(0, 300))
            next_step_date = created + dt.timedelta(days=rnd.randint(3, 30))
            deals.append(Deal.objects.create(
                name=f'{company.full_name} — {rnd.choice(["MSP onboarding", "Network refresh", "M365 migration", "Security package", "VoIP rollout"])}',
                next_step=rnd.choice(DEAL_STEPS),
                next_step_date=next_step_date,
                amount=Decimal(rnd.randrange(1500, 45000, 250)),
                currency=usd,
                stage=stage,
                probability=100 if success else rnd.choice([10, 25, 40, 60, 75]),
                company=company,
                contact=contact,
                owner=owner_for(company.department),
                department=company.department,
                closing_date=next_step_date + dt.timedelta(days=rnd.randint(10, 60)),
                description='Demo deal created by seed_demo.',
                ticket=f'MG-{2000 + i}',  # unique=True on Deal, default '' collides
                active=not success,
                relevant=True,
                important=rnd.random() < 0.15,
            ))

        # ---- payments on won deals ----------------------------------------
        payments = 0
        for deal in deals:
            if not getattr(deal.stage, 'success_stage', False):
                continue
            for n in range(rnd.randint(1, 3)):
                Payment.objects.create(
                    deal=deal,
                    amount=deal.amount / 3,
                    currency=usd,
                    payment_date=dt.date(2026, 1, 15) + dt.timedelta(days=rnd.randint(0, 280)),
                    status='r',
                    contract_number=f'C-{deal.id:04d}',
                    invoice_number=f'INV-{deal.id:04d}-{n + 1}',
                )
                payments += 1

        # ---- products -----------------------------------------------------
        products = []
        for name, price in [
            ('Managed workstation', 65), ('Managed server', 250), ('M365 Business Premium', 22),
            ('Backup per endpoint', 12), ('Security awareness training', 4),
            ('Firewall management', 95), ('VoIP seat', 25), ('Onboarding project', 2500),
        ]:
            products.append(Product.objects.create(
                name=name,
                description=f'Demo product: {name}.',
                price=Decimal(price),
                currency=usd,
                department=global_sales,
                on_sale=True,
            ))

        # ---- requests -----------------------------------------------------
        requests = []
        for i in range(options['requests']):
            first, last = contact_person()
            lead = rnd.choice(leads)
            company = rnd.choice(companies)
            req_dept = global_sales if rnd.random() < 0.7 else local_sales
            requests.append(Request.objects.create(
                request_for=rnd.choice(REQUEST_SUBJECTS),
                first_name=first,
                last_name=last,
                email=f'{first.lower()}.{last.lower()}{i}@request.example',
                phone=f'970-555-{rnd.randint(1000, 9999)}',
                company_name=company.full_name,
                company=company,
                lead=lead if rnd.random() < 0.4 else None,
                receipt_date=dt.date(2026, 2, 1) + dt.timedelta(days=rnd.randint(0, 260)),
                description=rnd.choice(LEAD_NOTES),
                owner=owner_for(req_dept),
                department=req_dept,
                pending=rnd.random() < 0.5,
                lead_source=rnd.choice(lead_sources) if lead_sources else None,
                country=rnd.choice(countries) if countries else None,
                city_name=rnd.choice(CITIES)[0],
            ))

        # ---- projects + tasks ---------------------------------------------
        projects = []
        for name, stage in [
            ('Q4 onboarding wave', project_stages[1] if len(project_stages) > 1 else None),
            ('Backup remediation', project_stages[1] if len(project_stages) > 1 else None),
            ('Network refresh — Loveland', project_stages[0] if project_stages else None),
            ('Security training rollout', project_stages[2] if len(project_stages) > 2 else None),
        ]:
            projects.append(Project.objects.create(
                name=name,
                next_step='Check the checklist',
                next_step_date=dt.date(2026, 11, 20),
                stage=stage,
                owner=rnd.choice(owners),
                description='Demo project created by seed_demo.',
                start_date=dt.date(2026, 8, 1),
                due_date=dt.date(2026, 12, 15),
            ))

        tasks = []
        for i in range(options['tasks']):
            if i % 3 == 0 and projects:
                project = rnd.choice(projects)
            else:
                project = None
            stage = rnd.choice(task_stages) if task_stages else None
            tasks.append(Task.objects.create(
                name=f'{rnd.choice(TASK_NAMES)} — {rnd.choice(companies).full_name}',
                description='Demo task created by seed_demo.',
                next_step='Do the thing',
                next_step_date=dt.date(2026, 11, 10) + dt.timedelta(days=rnd.randint(0, 45)),
                due_date=dt.date(2026, 11, 5) + dt.timedelta(days=rnd.randint(0, 50)),
                start_date=dt.date(2026, 10, 20),
                stage=stage,
                project=project,
                priority=rnd.choice(['1', '2', '3']),
                owner=rnd.choice(owners),
                active=True,
            ))

        # ---- emails -------------------------------------------------------
        emails = 0
        for i in range(25):
            lead = rnd.choice(leads)
            incoming = rnd.random() < 0.5
            CrmEmail.objects.create(
                subject=f'Re: {rnd.choice(REQUEST_SUBJECTS)}',
                content=f'Demo email body {i}. Ask about timelines and budget.',
                from_field=lead.email if incoming else 'crm@millenniumgroup.example',
                to=manager.email or 'sales@millenniumgroup.example' if incoming else lead.email,
                sent=not incoming,
                incoming=incoming,
                lead=lead,
                owner=manager,
                department=lead.department,
                is_html=False,
                ticket=f'demo-{i:03d}',
            )
            emails += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nseeded: {len(companies)} companies, {len(contacts)} contacts, '
            f'{len(leads)} leads, {len(deals)} deals, {payments} payments, '
            f'{len(products)} products, {len(requests)} requests, '
            f'{len(projects)} projects, {len(tasks)} tasks, {emails} emails'
        ))
        self.stdout.write(
            f'demo reps (password {DEMO_PASSWORD}): '
            + ', '.join(u.username for u in reps)
        )
        self.stdout.write(f'sales manager: {manager.username}')

    # ------------------------------------------------------------------ #
    def _ensure_reps(self, global_sales, local_sales):
        """Three extra sales users so per-rep filtering is visible."""
        co_workers = Group.objects.filter(name='co-workers').first()
        # Without a role group the reps authenticate but every admin view 403s:
        # permissions in this CRM come from the role groups, not the department.
        operators = Group.objects.filter(name='operators').first()
        specs = [
            ('rep.amara', 'Amara', 'Nwosu', global_sales),
            ('rep.diego', 'Diego', 'Salazar', local_sales),
            ('rep.ines', 'Ines', 'Kovac', global_sales),
        ]
        users = []
        for username, first, last, dept in specs:
            user, created = User.objects.get_or_create(
                username=username,
                defaults=dict(
                    email=f'{username}@millenniumgroup.example',
                    first_name=first,
                    last_name=last,
                    is_staff=True,
                ),
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save()
            groups = [g for g in (operators, co_workers, dept.group_ptr) if g is not None]
            user.groups.add(*groups)
            users.append(user)
        return users
