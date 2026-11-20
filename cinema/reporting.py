from decimal import Decimal

from django.db.models import Count, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from .access import EXPLOITATION, requires_role
from .inventory import with_inventory
from .models import Screening, Ticket
from .programme import selected_date
from .web_forms import RoomFilter


def occupancy(day, room=None):
    checkins = (
        Ticket.objects.filter(reservation__screening_id=OuterRef("pk"), used_at__isnull=False)
        .order_by().values("reservation__screening_id").annotate(count=Count("pk")).values("count")
    )
    screenings = Screening.objects.filter(status=Screening.Status.PUBLISHED, starts_at__date=day)
    if room:
        screenings = screenings.filter(room=room)
    screenings = with_inventory(screenings.select_related("film", "room")).annotate(
        admitted=Coalesce(Subquery(checkins), 0),
    )
    for screening in screenings:
        screening.fill_rate = Decimal(100 * screening.admitted) / screening.capacity
        yield screening


@requires_role(EXPLOITATION)
@never_cache
@require_safe
def dashboard(request):
    day = selected_date(request)
    form = RoomFilter(request.GET or None)
    room = form.cleaned_data.get("room") if form.is_valid() else None
    return render(request, "dashboard.html", {"day": day, "form": form, "screenings": list(occupancy(day, room))})
