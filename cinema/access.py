from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

GUICHET = "Guichet"
ACCUEIL = "Accueil"
PROGRAMMATION = "Programmation"
EXPLOITATION = "Exploitation"
ROLES = (GUICHET, ACCUEIL, PROGRAMMATION, EXPLOITATION)


def has_role(user, *roles):
    return bool(user.is_authenticated and (
        user.is_superuser or not set(roles).isdisjoint(user.groups.values_list("name", flat=True))
    ))


def requires_role(role):
    def decorate(view):
        @login_required
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not has_role(request.user, role):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapped

    return decorate


def navigation(request):
    user = request.user
    if not user.is_authenticated:
        return {}
    groups = set(ROLES) if user.is_superuser else set(user.groups.values_list("name", flat=True))
    return {
        "gestion": not groups.isdisjoint(ROLES),
        "guichet": GUICHET in groups, "accueil": ACCUEIL in groups,
        "programmation": PROGRAMMATION in groups, "exploitation": EXPLOITATION in groups,
    }
