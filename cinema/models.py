import uuid


from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class Film(models.Model):
    title = models.CharField("titre", max_length=120, unique=True)
    genre = models.CharField(max_length=45)
    duration = models.PositiveSmallIntegerField("durée en minutes")
    description = models.TextField("synopsis")
    artwork = models.PositiveSmallIntegerField(default=0)
    featured = models.BooleanField(default=False)

    class Meta:
        ordering = ["title"]
        constraints = [models.CheckConstraint(condition=Q(duration__gt=0), name="film_duration_positive")]

    def __str__(self):
        return self.title


class Room(models.Model):
    name = models.CharField("nom", max_length=60, unique=True)
    format = models.CharField("type de salle", max_length=40)
    capacity = models.PositiveSmallIntegerField("capacité")

    class Meta:
        ordering = ["name"]
        constraints = [models.CheckConstraint(condition=Q(capacity__gt=0), name="room_capacity_positive")]

    def __str__(self):
        return self.name


class Screening(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Brouillon"
        PUBLISHED = "published", "Publiée"
        CANCELLED = "cancelled", "Annulée"

    film = models.ForeignKey(Film, on_delete=models.PROTECT, verbose_name="film")
    room = models.ForeignKey(Room, on_delete=models.PROTECT, verbose_name="salle")
    starts_at = models.DateTimeField("début")
    ends_at = models.DateTimeField("fin")
    capacity = models.PositiveSmallIntegerField("jauge")
    price = models.DecimalField("tarif par place", max_digits=6, decimal_places=2)
    status = models.CharField("statut", max_length=10, choices=Status, default=Status.DRAFT)
    revision = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["starts_at", "pk"]
        indexes = [models.Index(fields=["status", "starts_at"]), models.Index(fields=["room", "starts_at"])]
        constraints = [
            models.CheckConstraint(condition=Q(ends_at__gt=F("starts_at")), name="screening_end_after_start"),
            models.CheckConstraint(condition=Q(capacity__gt=0), name="screening_capacity_positive"),
            models.CheckConstraint(condition=Q(price__gte=0), name="screening_price_nonnegative"),
        ]

    @property
    def starts_at_local_date(self):
        return timezone.localdate(self.starts_at).isoformat()

    @property
    def available(self):
        return max(0, self.capacity - self.allocated)

    @property
    def future(self):
        return self.starts_at > timezone.now()

    def __str__(self):
        return f"{self.film} · {timezone.localtime(self.starts_at):%d/%m/%Y %H:%M}"


class Reservation(models.Model):
    class Status(models.TextChoices):
        RESERVED = "reserved", "Réservée"
        PAID = "paid", "Réglée"
        EXPIRED = "expired", "Expirée"
        CANCELLED = "cancelled", "Annulée"

    class Channel(models.TextChoices):
        WEB = "web", "En ligne"
        DESK = "desk", "Guichet"

    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    request_key = models.UUIDField(unique=True, editable=False)
    screening = models.ForeignKey(Screening, on_delete=models.PROTECT, related_name="reservations")
    customer = models.ForeignKey(
        "auth.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="reservations",
    )
    created_by = models.ForeignKey("auth.User", null=True, on_delete=models.SET_NULL, related_name="+")
    quantity = models.PositiveSmallIntegerField("places")
    unit_price = models.DecimalField("tarif unitaire", max_digits=6, decimal_places=2)
    channel = models.CharField(max_length=4, choices=Channel)
    status = models.CharField(max_length=10, choices=Status)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["screening", "status", "expires_at"])]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name="reservation_quantity_positive"),
            models.CheckConstraint(condition=Q(unit_price__gte=0), name="reservation_price_nonnegative"),
        ]

    @property
    def effective_status(self):
        if self.status == self.Status.RESERVED and self.expires_at <= timezone.now():
            return self.Status.EXPIRED
        return self.status

    @property
    def effective_label(self):
        return self.Status(self.effective_status).label

    @property
    def total(self):
        return self.quantity * self.unit_price


class Ticket(models.Model):
    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    reservation = models.ForeignKey(Reservation, on_delete=models.PROTECT, related_name="tickets")
    used_at = models.DateTimeField(null=True, blank=True)
    checked_by = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["pk"]


class ScheduleChange(models.Model):
    screening = models.ForeignKey(Screening, on_delete=models.PROTECT, related_name="changes")
    actor = models.ForeignKey("auth.User", null=True, on_delete=models.SET_NULL)
    before = models.JSONField()
    after = models.JSONField()
    affected_bookings = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
