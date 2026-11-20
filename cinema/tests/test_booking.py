import json
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from uuid import uuid4

from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from cinema.access import GUICHET
from cinema.inventory import allocated_seats
from cinema.models import Reservation, Screening
from cinema.reservations import BookingError, cancel_booking, check_ticket, register_payment

from .factories import booking, session, user


class BookingTests(TestCase):
    def setUp(self):
        self.screening = session(capacity=2)
        self.customer = user()

    def test_reserve_two_places_and_generate_distinct_tickets(self):
        reservation = booking(self.screening, self.customer, quantity=2)
        self.assertEqual(reservation.status, Reservation.Status.RESERVED)
        self.assertEqual(reservation.total, Decimal("19.00"))
        self.assertEqual(allocated_seats(self.screening, timezone.now()), 2)
        self.assertEqual(len(set(reservation.tickets.values_list("reference", flat=True))), 2)

    def test_refused_quantity_leaves_stock_unchanged(self):
        booking(self.screening, self.customer)
        with self.assertRaisesMessage(BookingError, "pas assez de places"):
            booking(self.screening, user(), quantity=2)
        self.assertEqual(Reservation.objects.count(), 1)
        self.assertEqual(allocated_seats(self.screening, timezone.now()), 1)

    def test_publication_and_cutoff_rules(self):
        near = session(starts=timezone.now() + timedelta(minutes=5))
        draft = session(status=Screening.Status.DRAFT)
        with self.assertRaisesMessage(BookingError, "en ligne sont closes"):
            booking(near, self.customer)
        with self.assertRaisesMessage(BookingError, "ne peut plus être réservée"):
            booking(draft, self.customer)
        with self.assertRaisesMessage(BookingError, "entre 1 et 10"):
            booking(self.screening, self.customer, quantity=0)
        sale = booking(near, user(), channel=Reservation.Channel.DESK)
        self.assertEqual(sale.status, Reservation.Status.PAID)

    def test_retry_same_uuid_and_reject_different_payload(self):
        key = uuid4()
        first = booking(self.screening, self.customer, request_key=key)
        second = booking(self.screening, self.customer, request_key=key)
        self.assertEqual(first.reference, second.reference)
        with self.assertRaisesMessage(BookingError, "déjà utilisée"):
            booking(self.screening, self.customer, quantity=2, request_key=key)
        with self.assertRaisesMessage(BookingError, "déjà utilisée"):
            booking(self.screening, user(), request_key=key)
        self.assertEqual(Reservation.objects.count(), 1)

    def test_guichet_and_web_share_stock(self):
        booking(self.screening, self.customer)
        sale = booking(self.screening, user(), channel=Reservation.Channel.DESK)
        self.assertIsNone(sale.customer)
        self.assertEqual(sale.tickets.count(), 1)
        self.assertIsNotNone(sale.paid_at)
        with self.assertRaisesMessage(BookingError, "pas assez de places"):
            booking(self.screening, self.customer)
        self.assertEqual(allocated_seats(self.screening, timezone.now()), 2)

    def test_expiration_releases_stock_once(self):
        reservation = booking(self.screening, self.customer, quantity=2)
        reservation.expires_at = timezone.now() - timedelta(seconds=1)
        reservation.save(update_fields=["expires_at"])
        self.assertEqual(reservation.effective_status, Reservation.Status.EXPIRED)
        self.assertEqual(allocated_seats(self.screening, timezone.now()), 0)
        out = StringIO()
        call_command("expire_reservations", stdout=out)
        call_command("expire_reservations", stdout=out)
        self.assertIn("1 réservation", out.getvalue())
        self.assertIn("0 réservation", out.getvalue())
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.EXPIRED)
        with self.assertRaisesMessage(BookingError, "a expiré"):
            register_payment(reservation.reference)
        with self.assertRaisesMessage(BookingError, "a expiré"):
            check_ticket(reservation.tickets.first().reference, self.screening.pk, self.customer)
        booking(self.screening, user(), quantity=2)

    def test_register_payment_and_check_ticket_once(self):
        reservation = booking(self.screening, self.customer)
        ticket = reservation.tickets.get()
        with self.assertRaisesMessage(BookingError, "n’est pas réglé"):
            check_ticket(ticket.reference, self.screening.pk, self.customer)
        self.assertTrue(register_payment(reservation.reference))
        self.assertFalse(register_payment(reservation.reference))
        self.assertEqual(allocated_seats(self.screening, timezone.now()), 1)
        with self.assertRaisesMessage(BookingError, "autre séance"):
            check_ticket(ticket.reference, session().pk, self.customer)
        self.assertEqual(check_ticket(ticket.reference, self.screening.pk, self.customer).pk, ticket.pk)
        with self.assertRaisesMessage(BookingError, "déjà été utilisé"):
            check_ticket(ticket.reference, self.screening.pk, self.customer)
        with self.assertRaisesMessage(BookingError, "ne peut plus être annulée"):
            cancel_booking(reservation.reference, self.customer)

    def test_download_ticket_scope_pdf_and_confirmation(self):
        reservation = booking(self.screening, self.customer, quantity=2)
        ticket = reservation.tickets.first()
        route = reverse("download_ticket", args=[ticket.reference])
        self.assertEqual(self.client.get(route).status_code, 302)
        self.client.force_login(user())
        self.assertEqual(self.client.get(route).status_code, 404)
        self.client.force_login(self.customer)
        detail = self.client.get(reverse("booking_detail", args=[reservation.reference]))
        self.assertContains(detail, "Caisse dédiée du Grand Cinéma")
        self.assertContains(detail, "Télécharger le PDF", count=2)
        response = self.client.get(route)
        self.assertEqual(response.headers["Content-Type"], "application/pdf")
        self.assertTrue(b"".join(response.streaming_content).startswith(b"%PDF-"))
        self.client.force_login(user(roles=[GUICHET]))
        self.assertEqual(self.client.get(route).status_code, 200)

    def test_api_documentation_and_csrf(self):
        api = Client(enforce_csrf_checks=True)
        target = "/api/reservations/"
        body = json.dumps({"screening_id": self.screening.pk, "quantity": 1, "request_key": str(uuid4())})
        response = api.get("/api/openapi.json")
        self.assertEqual(response.status_code, 200)
        self.assertIn(target, response.json()["paths"])
        self.assertEqual(api.get("/api/docs").status_code, 200)
        self.assertEqual(api.post(target, body, content_type="application/json").status_code, 403)
        api.get(reverse("login"))
        anonymous_token = api.cookies["csrftoken"].value
        self.assertEqual(api.post(
            target, body, content_type="application/json", HTTP_X_CSRFTOKEN=anonymous_token,
        ).status_code, 401)
        api.force_login(self.customer)
        self.assertEqual(api.post(target, body, content_type="application/json").status_code, 403)
        api.get(reverse("book", args=[self.screening.pk]))
        token = api.cookies["csrftoken"].value
        response = api.post(target, body, content_type="application/json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["quantity"], 1)
        self.assertEqual(response.json()["status"], "reserved")
        retry = api.post(target, body, content_type="application/json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(response.json()["reference"], retry.json()["reference"])

    def test_public_programme_excludes_drafts_cancelled_and_other_day(self):
        day = timezone.localdate(self.screening.starts_at)
        draft = session(starts=self.screening.starts_at, status=Screening.Status.DRAFT)
        cancelled = session(starts=self.screening.starts_at, status=Screening.Status.CANCELLED)
        other_date = session(starts=self.screening.starts_at + timedelta(days=1))
        response = self.client.get(reverse("programme"), {"date": day})
        self.assertContains(response, self.screening.film.title)
        self.assertContains(response, "Grand écran")
        self.assertNotContains(response, draft.film.title)
        self.assertNotContains(response, cancelled.film.title)
        self.assertNotContains(response, other_date.film.title)
        self.assertContains(response, "2 places disponibles")
        booking(self.screening, user(), channel=Reservation.Channel.DESK)
        self.assertContains(self.client.get(reverse("programme"), {"date": day}), "1 place disponible")
        booking(self.screening, self.customer)
        self.assertContains(self.client.get(reverse("programme"), {"date": day}), "Complet")
        self.assertContains(self.client.get(reverse("programme"), {"date": day + timedelta(days=2)}),
                            "Aucune séance publiée")

    def test_browser_booking_failure_and_confirmation(self):
        route = reverse("book", args=[self.screening.pk])
        self.client.force_login(self.customer)
        self.assertContains(self.client.get(route), "Heure limite")
        self.assertEqual(self.client.post(route, {"quantity": 0}).status_code, 400)
        booking(self.screening, user())
        payload = {"quantity": 2, "request_key": str(uuid4())}
        self.assertContains(self.client.post(route, payload), "pas assez de places", status_code=409)
        payload["quantity"] = 1
        response = self.client.post(route, payload, follow=True)
        self.assertContains(response, "Billets numériques")
        ref = Reservation.objects.get(customer=self.customer).reference
        self.assertRedirects(self.client.post(route, payload), reverse("booking_detail", args=[ref]))

    def test_reserved_demo_names_cannot_be_registered(self):
        self.assertContains(self.client.post(reverse("signup"), {
            "username": "Equipe", "password1": "Mock-User-7759!", "password2": "Mock-User-7759!",
        }), "Ce nom est réservé")
        response = self.client.post(reverse("signup"), {
            "username": "cinéphile", "password1": "Mock-User-7759!", "password2": "Mock-User-7759!",
        }, follow=True)
        self.assertContains(response, "Mes réservations")
