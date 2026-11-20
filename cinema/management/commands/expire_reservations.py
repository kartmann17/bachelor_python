from django.core.management.base import BaseCommand
from django.utils import timezone

from cinema.models import Reservation


class Command(BaseCommand):
    help = "Enregistre les expirations des réservations non réglées."

    def handle(self, *args, **options):
        count = Reservation.objects.filter(
            status=Reservation.Status.RESERVED, expires_at__lte=timezone.now(),
        ).update(status=Reservation.Status.EXPIRED)
        self.stdout.write(f"{count} réservation(s) expirée(s).")
