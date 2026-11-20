from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone

from cinema.models import Film, Reservation, Room, Screening
from cinema.reservations import reserve


def user(name=None, roles=()):
    account = get_user_model().objects.create_user(username=name or uuid4().hex)
    for name in roles:
        account.groups.add(Group.objects.get_or_create(name=name)[0])
    return account


def session(*, capacity=100, status=Screening.Status.PUBLISHED, starts=None, film=None, room=None):
    starts = starts or timezone.now() + timedelta(hours=2)
    film = film or Film.objects.create(
        title=f"Film {uuid4().hex[:8]}", genre="Drame", duration=90, description="Synopsis de test",
    )
    room = room or Room.objects.create(name=f"Salle {uuid4().hex[:8]}", format="Grand écran", capacity=120)
    return Screening.objects.create(
        film=film, room=room, starts_at=starts, ends_at=starts + timedelta(minutes=film.duration),
        capacity=capacity, price=Decimal("9.50"), status=status,
    )


def booking(screening, account, quantity=1, channel=Reservation.Channel.WEB, request_key=None):
    return reserve(
        screening_id=screening.pk, user=account, quantity=quantity,
        request_key=request_key or uuid4(), channel=channel,
    )[0]
