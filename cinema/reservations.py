import logging
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from .inventory import allocated_seats
from .models import Reservation, Screening, Ticket

logger = logging.getLogger(__name__)
MAX_PLACES = 10
PAYMENT_LEAD = timedelta(minutes=15)
PAYMENT_LOCATION = "Caisse dédiée du Grand Cinéma"


class BookingError(Exception):
    def __init__(self, message, status=409):
        super().__init__(message)
        self.status = status


def payment_deadline(screening):
    return screening.starts_at - PAYMENT_LEAD


def _verify_retry(reservation, screening_id, user, quantity, channel):
    if (
        reservation.created_by_id != user.pk or reservation.screening_id != screening_id
        or reservation.quantity != quantity or reservation.channel != channel
    ):
        raise BookingError("Cette clé de demande est déjà utilisée pour une autre opération.")
    return reservation


@transaction.atomic
def reserve(*, screening_id, user, quantity, request_key, channel=Reservation.Channel.WEB):
    if not 1 <= quantity <= MAX_PLACES:
        raise BookingError(f"Choisissez entre 1 et {MAX_PLACES} places.", status=400)

    screening = Screening.objects.select_for_update().filter(pk=screening_id).first()
    if screening is None:
        raise BookingError("Séance introuvable.", status=404)
    existing = Reservation.objects.filter(request_key=request_key).first()
    if existing:
        return _verify_retry(existing, screening_id, user, quantity, channel), False

    now = timezone.now()
    is_web = channel == Reservation.Channel.WEB
    if screening.status != Screening.Status.PUBLISHED or screening.starts_at <= now:
        raise BookingError("Cette séance ne peut plus être réservée.")
    if is_web and payment_deadline(screening) <= now:
        raise BookingError("Les réservations en ligne sont closes. Adressez-vous au guichet.")
    if quantity > screening.capacity - allocated_seats(screening, now):
        raise BookingError("Il ne reste pas assez de places pour cette séance.")

    try:
        with transaction.atomic():
            booking = Reservation.objects.create(
                request_key=request_key, screening=screening, customer=user if is_web else None,
                created_by=user, quantity=quantity, unit_price=screening.price, channel=channel,
                status=Reservation.Status.RESERVED if is_web else Reservation.Status.PAID,
                expires_at=payment_deadline(screening) if is_web else None,
                paid_at=None if is_web else now,
            )
    except IntegrityError:
        existing = Reservation.objects.filter(request_key=request_key).first()
        if existing is None:
            raise
        return _verify_retry(existing, screening_id, user, quantity, channel), False

    Ticket.objects.bulk_create([Ticket(reservation=booking) for _ in range(quantity)])
    logger.info("reservation_created channel=%s screening=%s quantity=%s", channel, screening_id, quantity)
    return booking, True


def locked_booking(reference):
    # A single lock order: screening before any mutation of a reservation or ticket.
    screening_id = Reservation.objects.filter(reference=reference).values_list("screening_id", flat=True).first()
    if screening_id is None:
        raise BookingError("Référence de réservation introuvable.", status=404)
    Screening.objects.select_for_update().get(pk=screening_id)
    return Reservation.objects.select_for_update(of=("self",)).select_related("screening").get(reference=reference)


@transaction.atomic
def register_payment(reference):
    booking = locked_booking(reference)
    if booking.effective_status == Reservation.Status.EXPIRED:
        raise BookingError("Cette réservation a expiré. Les places ont été libérées.")
    if booking.screening.status != Screening.Status.PUBLISHED or booking.status == Reservation.Status.CANCELLED:
        raise BookingError("Cette réservation a été annulée.")
    if booking.status == Reservation.Status.PAID:
        return False
    now = timezone.now()
    if booking.expires_at <= now:
        raise BookingError("Cette réservation a expiré. Les places ont été libérées.")
    booking.status = Reservation.Status.PAID
    booking.paid_at = now
    booking.save(update_fields=["status", "paid_at"])
    logger.info("payment_registered screening=%s", booking.screening_id)
    return True


@transaction.atomic
def check_ticket(reference, screening_id, agent):
    screening = Screening.objects.select_for_update().get(pk=screening_id)
    ticket = (
        Ticket.objects.select_related("reservation")
        .filter(reference=reference)
        .first()
    )
    if ticket is None:
        raise BookingError("Ce billet est introuvable.", status=404)
    booking = ticket.reservation
    if booking.screening_id != screening.pk:
        raise BookingError("Ce billet correspond à une autre séance.")
    if ticket.used_at:
        raise BookingError("Ce billet a déjà été utilisé.")
    if booking.status == Reservation.Status.CANCELLED or screening.status != Screening.Status.PUBLISHED:
        raise BookingError("Ce billet a été annulé.")
    if booking.effective_status == Reservation.Status.EXPIRED:
        raise BookingError("Ce billet a expiré.")
    if booking.status != Reservation.Status.PAID:
        raise BookingError("Ce billet n’est pas réglé.")
    ticket.used_at = timezone.now()
    ticket.checked_by = agent
    ticket.save(update_fields=["used_at", "checked_by"])
    logger.info("ticket_checked screening=%s", screening.pk)
    return ticket
