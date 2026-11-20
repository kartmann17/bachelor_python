from django.db.models import Q, Sum
from django.utils import timezone

from .models import Reservation


def active_reservations(at):
    return Q(status=Reservation.Status.PAID) | Q(status=Reservation.Status.RESERVED, expires_at__gt=at)


def with_inventory(screenings, at=None):
    at = at or timezone.now()
    active = Q(reservations__status=Reservation.Status.PAID) | Q(
        reservations__status=Reservation.Status.RESERVED, reservations__expires_at__gt=at,
    )
    return screenings.annotate(allocated=Sum("reservations__quantity", filter=active, default=0))


def allocated_seats(screening, at):
    return screening.reservations.filter(active_reservations(at)).aggregate(
        quantity=Sum("quantity", default=0)
    )["quantity"]
