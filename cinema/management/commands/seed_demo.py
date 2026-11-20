import os
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from cinema.access import ROLES
from cinema.models import Film, Room, Screening

FILMS = (
    ("Dernier Métro", "Thriller", 104, "Dans le dernier métro parisien, une passagère découvre un secret qui aurait dû rester sous terre."),
    ("Une nuit en bleu", "Drame musical", 97, "À la veille du festival, un saxophoniste revient jouer dans le club où tout a commencé."),
    ("Au-delà des cimes", "Aventure", 112, "Deux amis traversent les Alpes et renouent avec un rêve qu’ils avaient abandonné."),
    ("Les jours d’été", "Drame", 93, "Sur la côte méditerranéenne, une jeune femme retrouve sa famille le temps d’un été."),
)
CAPACITIES = (300, 240, 210, 180, 160, 150, 140, 120, 110, 90)
TIMES = (
    (time(15, 20), time(18, 15), time(22, 55)),
    (time(16, 0), time(19, 15), time(23, 5)),
    (time(14, 45), time(18, 40), time(23, 15)),
    (time(15, 45), time(20, 10), time(23, 25)),
)


class Command(BaseCommand):
    help = "Crée le programme et les deux comptes de démonstration sur une base de test."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=14)
        parser.add_argument("--reset-passwords", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        days = options["days"]
        if not 1 <= days <= 60:
            raise CommandError("Choisissez une durée de 1 à 60 jours.")
        groups = [Group.objects.get_or_create(name=name)[0] for name in ROLES]
        for username, key, local_password in (
            ("spectateur", "DEMO_SPECTATOR_PASSWORD", "Seance-Metro-2026!"),
            ("equipe", "DEMO_STAFF_PASSWORD", "Guichet-Cinema-2026!"),
        ):
            user, created = get_user_model().objects.get_or_create(username=username)
            if created or options["reset_passwords"]:
                password = os.getenv(key) or (local_password if settings.DEBUG else "")
                if not password:
                    raise CommandError(f"Renseignez {key} pour initialiser le compte.")
                try:
                    validate_password(password, user)
                except ValidationError as exc:
                    raise CommandError(f"{key} : {' '.join(exc.messages)}") from exc
                user.set_password(password)
                user.save(update_fields=["password"])
            if username == "equipe":
                if not created and not user.groups.filter(name__in=ROLES).exists() and not options["reset_passwords"]:
                    raise CommandError("Le compte equipe existe déjà. Vérifiez-le avant toute attribution de rôle.")
                user.groups.add(*groups)

        rooms = [
            Room.objects.get_or_create(
                name=f"Salle {index:02}",
                defaults={"capacity": capacity, "format": "Grand écran" if index <= 2 else "Standard"},
            )[0]
            for index, capacity in enumerate(CAPACITIES, start=1)
        ]
        films = [
            Film.objects.get_or_create(
                title=title, defaults={
                    "genre": genre, "duration": duration, "description": description,
                    "artwork": index, "featured": index == 1,
                },
            )[0]
            for index, (title, genre, duration, description) in enumerate(FILMS, start=1)
        ]
        created_count = 0
        today = timezone.localdate()
        for day_offset in range(days):
            day = today + timedelta(days=day_offset)
            for film_index, film in enumerate(films):
                room = rooms[film_index]
                for hour in TIMES[film_index]:
                    start = timezone.make_aware(datetime.combine(day, hour))
                    end = start + timedelta(minutes=film.duration)
                    screenings = Screening.objects.filter(room=room, starts_at__lt=end, ends_at__gt=start)
                    if screenings.exclude(status=Screening.Status.CANCELLED).exists():
                        continue
                    _, created = Screening.objects.get_or_create(
                        film=film, room=room, starts_at=start,
                        defaults={
                            "ends_at": end, "capacity": min(100, room.capacity), "price": Decimal("9.50"),
                            "status": Screening.Status.PUBLISHED,
                        },
                    )
                    created_count += int(created)
        self.stdout.write(self.style.SUCCESS(f"{created_count} séance(s) ajoutée(s). Comptes prêts."))
