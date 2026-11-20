from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from .inventory import active_reservations
from .models import Reservation, Room, ScheduleChange, Screening
from .reservations import PAYMENT_LEAD, BookingError, payment_deadline


def _end_time(data):
    return data["starts_at"] + timedelta(minutes=data["film"].duration)


def _validate_schedule(data, status, exclude=None):
    if not 1 <= data["capacity"] <= data["room"].capacity:
        raise BookingError("La jauge doit être comprise entre 1 et la capacité de la salle.")
    if data["starts_at"] <= timezone.now():
        raise BookingError("L’horaire de la séance doit être dans le futur.")
    if status == Screening.Status.PUBLISHED and Screening.objects.filter(
        room=data["room"], status=Screening.Status.PUBLISHED,
        starts_at__lt=_end_time(data), ends_at__gt=data["starts_at"],
    ).exclude(pk=exclude).exists():
        raise BookingError("Ce créneau chevauche une autre séance publiée dans cette salle.")


@transaction.atomic
def create_draft(data):
    _validate_schedule(data, Screening.Status.DRAFT)
    return Screening.objects.create(**data, ends_at=_end_time(data), status=Screening.Status.DRAFT)


def lock_scheduling_rooms():
    # Programming writes are infrequent; locking the ten rooms in a fixed order
    # makes a room change and simultaneous publications serialize safely.
    list(Room.objects.order_by("pk").select_for_update().values_list("pk", flat=True))


@transaction.atomic
def publish(screening_id):
    lock_scheduling_rooms()
    screening = Screening.objects.select_related("film", "room").select_for_update(of=("self",)).get(
        pk=screening_id,
    )
    if screening.status != Screening.Status.DRAFT:
        raise BookingError("Seul un brouillon peut être publié.")
    _validate_schedule({
        "room": screening.room, "film": screening.film,
        "capacity": screening.capacity, "starts_at": screening.starts_at,
    }, Screening.Status.PUBLISHED, exclude=screening.pk)
    screening.status = Screening.Status.PUBLISHED
    screening.revision += 1
    screening.save(update_fields=["status", "revision"])
    return screening


def snapshot(data):
    return {
        "film": data["film"].pk, "room": data["room"].pk,
        "starts_at": data["starts_at"].isoformat(), "capacity": data["capacity"], "price": str(data["price"]),
    }


def schedule_impact(screening, at=None):
    reservations = screening.reservations.filter(active_reservations(at or timezone.now()))
    return reservations.aggregate(bookings=Count("pk"), places=Sum("quantity", default=0))


@transaction.atomic
def update_screening(screening_id, data, actor, revision, expected_impact):
    lock_scheduling_rooms()
    screening = Screening.objects.select_related("film", "room").select_for_update(of=("self",)).get(
        pk=screening_id,
    )
    now = timezone.now()
    impact = schedule_impact(screening, now)
    if revision != screening.revision or expected_impact != impact:
        raise BookingError("La séance ou ses réservations ont changé. Vérifiez à nouveau l’impact.")
    if screening.status == Screening.Status.CANCELLED or screening.starts_at <= now:
        raise BookingError("Cette séance ne peut plus être modifiée.")
    if data["capacity"] < impact["places"]:
        raise BookingError("La jauge ne peut pas être inférieure aux places déjà attribuées.")
    _validate_schedule(data, screening.status, exclude=screening.pk)

    previous_deadline = payment_deadline(screening)
    next_deadline = data["starts_at"] - PAYMENT_LEAD
    pending = screening.reservations.filter(status=Reservation.Status.RESERVED, expires_at__gt=now)
    if previous_deadline != next_deadline:
        if next_deadline <= now and pending.exists():
            raise BookingError("Ce nouvel horaire ferait expirer des réservations actives.")
        pending.update(expires_at=next_deadline)

    before = snapshot({field: getattr(screening, field) for field in data})
    for field, value in data.items():
        setattr(screening, field, value)
    screening.ends_at = _end_time(data)
    screening.revision += 1
    screening.save()
    ScheduleChange.objects.create(
        screening=screening, actor=actor, before=before, after=snapshot(data),
        affected_bookings=impact["bookings"],
    )
    return screening
