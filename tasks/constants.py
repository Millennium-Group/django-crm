"""Constants shared by admin code and template tags.

Admin modules import heavyweight classes (unfold.admin); template tag
libraries must not, because they are loaded during Django setup while the
admin module itself is still initialising — that produced a circular import.
Anything both sides need belongs here.
"""
from django.utils.translation import gettext_lazy

COMPLETED_TITLE = gettext_lazy("I completed my part of the task")
