from django import forms
from django.utils import timezone

from .models import Room, Screening

from .reservations import MAX_PLACES


class BookingForm(forms.Form):
    quantity = forms.IntegerField(label="Nombre de places", min_value=1, max_value=MAX_PLACES)
    request_key = forms.UUIDField(widget=forms.HiddenInput)


def available_screenings():
    return Screening.objects.filter(
        status=Screening.Status.PUBLISHED, starts_at__gt=timezone.now(),
    ).select_related("film", "room")


class DeskSaleForm(BookingForm):
    screening = forms.ModelChoiceField(label="Séance", queryset=Screening.objects.none())
    field_order = ["screening", "quantity", "request_key"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = available_screenings()
        if self.is_bound:
            # A retry still reaches the service if the session has since started.
            queryset = Screening.objects.all().select_related("film", "room")
        self.fields["screening"].queryset = queryset


class BookingLookupForm(forms.Form):
    reference = forms.UUIDField(
        label="Référence de la réservation",
        widget=forms.TextInput(attrs={"autocomplete": "off", "spellcheck": "false"}),
        error_messages={"invalid": "Ce format de référence n’est pas valide."},
    )


class CheckTicketForm(BookingLookupForm):
    reference = forms.UUIDField(
        label="Référence du billet ou lecture QR",
        widget=forms.TextInput(attrs={"autocomplete": "off", "spellcheck": "false"}),
        error_messages={"invalid": "Ce format de référence de billet n’est pas valide."},
    )
    screening = forms.ModelChoiceField(label="Séance contrôlée", queryset=Screening.objects.none())
    field_order = ["screening", "reference"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        self.fields["screening"].queryset = Screening.objects.filter(
            status=Screening.Status.PUBLISHED, starts_at__date=today,
        ).select_related("film", "room")


class ScreeningForm(forms.ModelForm):
    class Meta:
        model = Screening
        fields = ["film", "room", "starts_at", "capacity", "price"]
        widgets = {"starts_at": forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"})}


class RoomFilter(forms.Form):
    room = forms.ModelChoiceField(label="Salle", queryset=Room.objects.all(), empty_label="Toutes les salles", required=False)
