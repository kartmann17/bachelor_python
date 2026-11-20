from django import forms

from .reservations import MAX_PLACES


class BookingForm(forms.Form):
    quantity = forms.IntegerField(label="Nombre de places", min_value=1, max_value=MAX_PLACES)
    request_key = forms.UUIDField(widget=forms.HiddenInput)
