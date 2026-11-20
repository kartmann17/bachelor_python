from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cinema.access import ACCUEIL, EXPLOITATION, GUICHET, PROGRAMMATION
from cinema.models import Reservation, ScheduleChange, Screening, Ticket
from cinema.reporting import occupancy
from cinema.reservations import BookingError, cancel_booking
from cinema.scheduling import create_draft, publish, schedule_impact, update_screening

from .factories import booking, session, user


class WorkflowTests(TestCase):
    def setUp(self):
        self.screening = session()
        self.day = timezone.localdate(self.screening.starts_at)
        self.staff = user(roles=[GUICHET, ACCUEIL, PROGRAMMATION, EXPLOITATION])
        self.customer = user()

    def data(self, **changes):
        values = {
            "film": self.screening.film, "room": self.screening.room,
            "starts_at": self.screening.starts_at, "capacity": 100, "price": Decimal("9.50"),
        }
        return {**values, **changes}

    def test_draft_publication_and_room_conflict(self):
        draft = create_draft(self.data())
        self.assertEqual(draft.status, Screening.Status.DRAFT)
        with self.assertRaisesMessage(BookingError, "chevauche"):
            publish(draft.pk)
        with self.assertRaisesMessage(BookingError, "capacité de la salle"):
            create_draft(self.data(capacity=121))
        draft = create_draft(self.data(starts_at=self.screening.ends_at))
        self.assertEqual(publish(draft.pk).status, Screening.Status.PUBLISHED)
        with self.assertRaisesMessage(BookingError, "Seul un brouillon"):
            publish(draft.pk)

    def test_create_publish_via_web(self):
        self.client.force_login(self.staff)
        starts_at = timezone.localtime(self.screening.ends_at + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
        response = self.client.post(reverse("schedule_create"), {
            "film": self.screening.film_id, "room": self.screening.room_id, "starts_at": starts_at,
            "capacity": 70, "price": "8.60",
        }, follow=True)
        self.assertContains(response, "Brouillon créé")
        draft = Screening.objects.get(status=Screening.Status.DRAFT)
        result = self.client.post(reverse("schedule_publish", args=[draft.pk]), follow=True)
        self.assertContains(result, "Séance publiée")

    def test_change_shows_impact_blocks_low_capacity_and_audits_updates(self):
        reservation = booking(self.screening, self.customer, quantity=2)
        impact = schedule_impact(self.screening)
        self.assertEqual(impact, {"bookings": 1, "places": 2})
        with self.assertRaisesMessage(BookingError, "jauge ne peut pas être inférieure"):
            update_screening(self.screening.pk, self.data(capacity=1), self.staff, 0, impact)
        new_time = self.screening.starts_at + timedelta(hours=1)
        edited = update_screening(
            self.screening.pk, self.data(starts_at=new_time, capacity=3), self.staff, 0, impact,
        )
        reservation.refresh_from_db()
        self.assertEqual(reservation.expires_at, new_time - timedelta(minutes=15))
        self.assertEqual(edited.capacity, 3)
        self.assertEqual(ScheduleChange.objects.get().affected_bookings, 1)
        response = self.client.get(reverse("programme"), {"date": edited.starts_at_local_date})
        self.assertContains(response, timezone.localtime(new_time).strftime("%H:%M"))
        with self.assertRaisesMessage(BookingError, "ont changé"):
            update_screening(self.screening.pk, self.data(capacity=2), self.staff, 0, impact)

    def test_change_confirmation_checks_stale_impact_and_values(self):
        self.client.force_login(self.staff)
        route = reverse("schedule_edit", args=[self.screening.pk])
        starts_at = timezone.localtime(self.screening.starts_at + timedelta(minutes=12)).strftime("%Y-%m-%dT%H:%M")
        data = {
            "film": self.screening.film_id, "room": self.screening.room_id, "starts_at": starts_at,
            "capacity": 80, "price": "9.50",
        }
        response = self.client.post(route, data)
        self.assertContains(response, "Confirmer la modification")
        token = response.context["confirmation"]
        modified = self.client.post(route, {**data, "capacity": 81, "confirmation": token})
        self.assertEqual(modified.status_code, 409)
        booking(self.screening, self.customer)
        self.assertContains(self.client.post(route, {**data, "confirmation": token}), "ont changé", status_code=409)
        response = self.client.post(route, data)
        self.assertContains(response, "réservation active concernée")
        confirmed = self.client.post(route, {**data, "confirmation": response.context["confirmation"]}, follow=True)
        self.assertContains(confirmed, "changement a été journalisé")

    def test_dashboard_real_attendance_and_saturation_threshold(self):
        for count in (10, 10, 10, 10, 10, 10, 10, 10, 9):
            booking(self.screening, self.staff, quantity=count, channel=Reservation.Channel.DESK)
        collected = list(self.screening.reservations.values_list("tickets__pk", flat=True))[:72]
        Ticket.objects.filter(pk__in=collected).update(used_at=timezone.now())
        summary = next(occupancy(self.day))
        self.assertEqual((summary.allocated, summary.available, summary.admitted, summary.fill_rate), (89, 11, 72, 72))
        self.assertFalse(summary.saturated)
        extra = booking(self.screening, self.customer)
        self.assertTrue(next(occupancy(self.day)).saturated)
        self.assertTrue(cancel_booking(extra.reference, self.staff))
        self.assertFalse(cancel_booking(extra.reference, self.staff))
        self.assertFalse(next(occupancy(self.day)).saturated)
        self.assertFalse(list(occupancy(self.day + timedelta(days=1))))
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(reverse("dashboard"), {"date": self.day}), "72 %")
        other = session()
        self.assertNotContains(
            self.client.get(reverse("dashboard"), {"date": self.day, "room": self.screening.room_id}),
            other.film.title,
        )

    def test_screen_access_separate_roles(self):
        self.client.force_login(self.customer)
        for view in ("workspace", "desk_sale", "desk_lookup", "check_in", "schedule", "dashboard"):
            self.assertEqual(self.client.get(reverse(view)).status_code, 403, view)
        self.client.force_login(user(roles=[ACCUEIL]))
        self.assertEqual(self.client.get(reverse("desk_lookup")).status_code, 403)
        self.assertEqual(self.client.get(reverse("check_in")).status_code, 200)

    def test_end_to_end_guichet_and_entry_forms(self):
        self.client.force_login(self.staff)
        booking_result = self.client.post(reverse("desk_sale"), {
            "screening": self.screening.pk, "quantity": 1, "request_key": uuid4(),
        }, follow=True)
        self.assertContains(booking_result, "Réglée")
        web_booking = booking(self.screening, self.customer)
        self.assertContains(
            self.client.get(reverse("desk_lookup"), {"reference": uuid4()}), "introuvable", status_code=400,
        )
        response = self.client.get(reverse("desk_lookup"), {"reference": web_booking.reference}, follow=True)
        self.assertContains(response, "Enregistrer le règlement")
        response = self.client.post(reverse("desk_pay", args=[web_booking.reference]), follow=True)
        self.assertContains(response, "Règlement enregistré")

        today = timezone.localdate(self.screening.starts_at)
        with patch("cinema.web_forms.timezone.localdate", return_value=today):
            details = {"screening": self.screening.pk, "reference": web_booking.tickets.get().reference}
            response = self.client.post(reverse("check_in"), details, follow=True)
            self.assertContains(response, "Entrée autorisée")
            duplicate = self.client.post(reverse("check_in"), details)
            self.assertContains(duplicate, "déjà été utilisé", status_code=409)

    def test_seed_demo_can_be_repeated(self):
        with self.settings(DEBUG=True):
            call_command("seed_demo", "--days", "1", stdout=StringIO())
            count = Screening.objects.count()
            call_command("seed_demo", "--days", "1", stdout=StringIO())
        self.assertEqual(Screening.objects.count(), count)
        team = get_user_model().objects.get(username="equipe")
        self.assertTrue(team.check_password("Guichet-Cinema-2026!"))
        self.assertSetEqual(set(team.groups.values_list("name", flat=True)), {GUICHET, ACCUEIL, PROGRAMMATION, EXPLOITATION})
