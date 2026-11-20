from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import Room, Screening
from .reservations import BookingError


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
