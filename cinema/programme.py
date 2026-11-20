from collections import defaultdict
from datetime import date, timedelta

from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_safe

from .inventory import with_inventory
from .models import Film, Screening


def selected_date(request):
    today = timezone.localdate()
    value = request.GET.get("date")
    if value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    return today


@require_safe
def programme(request):
    today = timezone.localdate()
    day = selected_date(request)
    screenings = with_inventory(
        Screening.objects.select_related("film", "room")
        .filter(status=Screening.Status.PUBLISHED, starts_at__date=day)
    )
    by_film = defaultdict(list)
    for screening in screenings:
        by_film[screening.film].append(screening)
    featured = Film.objects.filter(featured=True, pk__in=[film.pk for film in by_film]).first()
    start = day if day < today or day > today + timedelta(days=6) else today
    return render(request, "programme.html", {
        "day": day, "dates": [start + timedelta(days=i) for i in range(7)],
        "films": by_film.items(), "featured": featured,
        "featured_screening": next(
            (session for session in by_film.get(featured, []) if session.future), None,
        ),
    })
