"""Rewrite the project's admin.py modules to inherit from Unfold's base classes.

Unfold only styles forms/change lists when the ModelAdmin (and inline) classes
derive from ``unfold.admin.*``. Doing this by hand across ~40 classes invites
copy/paste mistakes, so the rewrite is scripted and reviewable.

Usage
-----
    python scripts/migrate_admin_to_unfold.py --dry-run   # show the diff only
    python scripts/migrate_admin_to_unfold.py             # apply

The rewrite is intentionally dumb and idempotent: it only touches the class
references ``admin.ModelAdmin`` / ``admin.TabularInline`` /
``admin.StackedInline`` and adds one import line per file that needs it.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Every module that can define a ModelAdmin: top-level admin.py files plus the
# custom admin classes under each app's site/ package (that is where the CRM
# actually keeps most of them).
APP_DIRS = [
    'analytics', 'api', 'chat', 'common', 'crm', 'help',
    'massmail', 'quality', 'settings', 'tasks', 'voip',
]

RENAMES = {
    'admin.ModelAdmin': 'UnfoldModelAdmin',
    'admin.TabularInline': 'UnfoldTabularInline',
    'admin.StackedInline': 'UnfoldStackedInline',
}

IMPORTS = {
    'admin.ModelAdmin': 'from unfold.admin import ModelAdmin as UnfoldModelAdmin  # noqa: E402\n',
    'admin.StackedInline': 'from unfold.admin import StackedInline as UnfoldStackedInline  # noqa: E402\n',
    'admin.TabularInline': 'from unfold.admin import TabularInline as UnfoldTabularInline  # noqa: E402\n'}

ANCHOR = 'from django.contrib import admin\n'


def migrate(path: pathlib.Path, dry_run: bool) -> list[str]:
    source = path.read_text(encoding='utf-8')
    if 'UnfoldModelAdmin' in source:
        return [f'{path}: already migrated, skipped']

    touched = []
    needed_imports = []
    new = source
    for old, replacement in RENAMES.items():
        if old in new:
            count = new.count(old)
            # Word boundary so admin.ModelAdminMixin-style names are untouched.
            new = new.replace(old + ')', replacement + ')')
            new = new.replace(old + ',', replacement + ',')
            new = new.replace(old + ':', replacement + ':')
            new = new.replace(old + ']', replacement + ']')
            new = new.replace(old + '\n', replacement + '\n')
            needed_imports.append(IMPORTS[old])
            touched.append(f'{path}: {old} -> {replacement} ({count} site(s))')

    # super(admin.ModelAdmin, self) must keep pointing at the Django base class
    new = new.replace('super(UnfoldModelAdmin,', 'super(admin.ModelAdmin,')

    if not touched:
        return [f'{path}: no admin base classes found']

    if ANCHOR in new:
        new = new.replace(ANCHOR, ANCHOR + ''.join(needed_imports), 1)
    else:
        # no canonical anchor: insert after the last top-level import
        lines = new.splitlines(keepends=True)
        last_import = 0
        for i, line in enumerate(lines[:80]):
            if line.startswith(('import ', 'from ')):
                last_import = i
        lines[last_import + 1:last_import + 1] = needed_imports
        new = ''.join(lines)

    if dry_run:
        import difflib

        diff = difflib.unified_diff(
            source.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=str(path),
            tofile=str(path) + ' (unfold)',
        )
        touched.extend(line.rstrip('\n') for line in diff if line.startswith(('+', '-')))

    if not dry_run:
        path.write_text(new, encoding='utf-8')
    return touched


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    targets = []
    for app in APP_DIRS:
        targets += sorted((ROOT / app).glob('admin.py'))
        targets += sorted((ROOT / app).glob('site/**/*.py'))

    report = []
    for path in targets:
        if path.name == '__init__.py' or '__pycache__' in str(path):
            continue
        if 'admin.ModelAdmin' not in path.read_text(encoding='utf-8'):
            continue
        report.extend(migrate(path, args.dry_run))

    print('\n'.join(report))
    if args.dry_run:
        print('\n(dry run — nothing written)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
