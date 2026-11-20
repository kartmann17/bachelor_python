import uuid

from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_http_methods, require_safe

from .access import ACCUEIL, EXPLOITATION, GUICHET, PROGRAMMATION, requires_any_role, requires_role
from .models import Reservation
from .reservations import PAYMENT_LOCATION, BookingError, register_payment, reserve
from .web_forms import BookingLookupForm, DeskSaleForm


@requires_any_role(GUICHET, ACCUEIL, PROGRAMMATION, EXPLOITATION)
@never_cache
@require_safe
def workspace(request):
    return render(request, "staff_home.html")


@requires_role(GUICHET)
@never_cache
@require_http_methods(["GET", "HEAD", "POST"])
def desk_sale(request):
    form = DeskSaleForm(
        request.POST if request.method == "POST" else None, initial={"request_key": uuid.uuid4(), "quantity": 1},
    )
    status = 200
    if request.method == "POST":
        if form.is_valid():
            try:
                booking, _ = reserve(
                    screening_id=form.cleaned_data["screening"].pk,
                    user=request.user, quantity=form.cleaned_data["quantity"],
                    request_key=form.cleaned_data["request_key"], channel=Reservation.Channel.DESK,
                )
                return redirect("desk_receipt", reference=booking.reference)
            except BookingError as exc:
                form.add_error(None, str(exc))
                status = exc.status
        else:
            status = 400
    return render(request, "staff_form.html", {
        "title": "Vente au guichet", "form": form, "submit": "Enregistrer la vente réglée",
        "description": "Encaissez le règlement avant de confirmer la vente.",
    }, status=status)


@requires_role(GUICHET)
@never_cache
@require_safe
def desk_receipt(request, reference):
    booking = get_object_or_404(
        Reservation.objects.select_related("screening__film", "screening__room").prefetch_related("tickets"),
        reference=reference,
    )
    return render(request, "desk_receipt.html", {"booking": booking, "payment_location": PAYMENT_LOCATION})


@requires_role(GUICHET)
@never_cache
@require_safe
def desk_lookup(request):
    form = BookingLookupForm(request.GET if "reference" in request.GET else None)
    if form.is_bound and form.is_valid():
        reference = form.cleaned_data["reference"]
        if Reservation.objects.filter(reference=reference).exists():
            return redirect("desk_receipt", reference=reference)
        form.add_error("reference", "Référence de réservation introuvable.")
    return render(request, "desk_lookup.html", {"form": form}, status=400 if form.errors else 200)


@requires_role(GUICHET)
@never_cache
@require_POST
def desk_pay(request, reference):
    try:
        if register_payment(reference):
            messages.success(request, "Règlement enregistré. Les billets sont maintenant réglés.")
        else:
            messages.info(request, "Cette réservation est déjà réglée.")
    except BookingError as exc:
        if exc.status == 404:
            raise Http404(str(exc)) from exc
        messages.error(request, str(exc))
    return redirect("desk_receipt", reference=reference)
