from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.db import connection, connections
from django.test import TransactionTestCase
from django.utils import timezone

from cinema.inventory import allocated_seats
from cinema.models import Reservation
from cinema.reservations import BookingError, check_ticket, register_payment

from .factories import booking, session, user


@skipUnless(connection.vendor == "postgresql", "Ces tests valident les verrous PostgreSQL.")
class ConcurrencyTests(TransactionTestCase):
    @staticmethod
    def race(first, second):
        gate = Barrier(2)

        def run(operation):
            try:
                gate.wait(timeout=10)
                operation()
                return 200
            except BookingError as exc:
                return exc.status
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run, operation) for operation in (first, second)]
            return sorted(future.result(timeout=20) for future in futures)

    def test_concurrent_web_reservations_last_place(self):
        screening = session(capacity=1)
        first, second = user(), user()
        self.assertEqual(self.race(lambda: booking(screening, first), lambda: booking(screening, second)), [200, 409])
        self.assertEqual(Reservation.objects.count(), 1)
        self.assertEqual(allocated_seats(screening, timezone.now()), 1)

    def test_desk_and_web_compete_for_last_place(self):
        screening = session(capacity=1)
        customer, clerk = user(), user()
        self.assertEqual(self.race(
            lambda: booking(screening, customer),
            lambda: booking(screening, clerk, channel=Reservation.Channel.DESK),
        ), [200, 409])
        self.assertEqual(Reservation.objects.count(), 1)

    def test_two_agents_cannot_admit_same_ticket(self):
        screening = session()
        reservation = booking(screening, user())
        register_payment(reservation.reference)
        first, second = user(), user()
        ticket = reservation.tickets.get()
        self.assertEqual(self.race(
            lambda: check_ticket(ticket.reference, screening.pk, first),
            lambda: check_ticket(ticket.reference, screening.pk, second),
        ), [200, 409])
        ticket.refresh_from_db()
        self.assertIn(ticket.checked_by_id, [first.pk, second.pk])
