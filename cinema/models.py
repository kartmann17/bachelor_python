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
    def future(self):
        return self.starts_at > timezone.now()

    def __str__(self):
        return f"{self.film} · {timezone.localtime(self.starts_at):%d/%m/%Y %H:%M}"
