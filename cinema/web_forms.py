from django import forms
from django.utils import timezone

from .models import Screening

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
