import uuid

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from .access import GUICHET, has_role
from .inventory import with_inventory
from .models import Reservation, Screening, Ticket
from .reservations import PAYMENT_LOCATION, BookingError, payment_deadline, reserve
from .ticket_pdf import ticket_pdf
from .web_forms import BookingForm


@require_http_methods(["GET", "HEAD", "POST"])
def signup(request):
    if request.user.is_authenticated:
        return redirect("programme")
    form = UserCreationForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        login(request, form.save())
        return redirect("programme")
    return render(request, "registration/signup.html", {"form": form})


@login_required
@never_cache
@require_http_methods(["GET", "HEAD", "POST"])
def book(request, screening_id):
    screening = get_object_or_404(
        with_inventory(Screening.objects.select_related("film", "room")),
        pk=screening_id, status=Screening.Status.PUBLISHED,
    )
    form = BookingForm(
        request.POST if request.method == "POST" else None, initial={"request_key": uuid.uuid4(), "quantity": 1}
    )
    status = 200
    if request.method == "POST":
        if form.is_valid():
            try:
                booking, _ = reserve(screening_id=screening.pk, user=request.user, **form.cleaned_data)
                return redirect("booking_detail", reference=booking.reference)
            except BookingError as exc:
                form.add_error(None, str(exc))
                status = exc.status
                screening = with_inventory(Screening.objects.select_related("film", "room")).get(pk=screening.pk)
        else:
            status = 400
    return render(request, "book.html", {
        "form": form, "screening": screening, "payment_deadline": payment_deadline(screening), "payment_location": PAYMENT_LOCATION,
        "can_book": payment_deadline(screening) > timezone.now() and screening.available > 0,
    }, status=status)


@login_required
@never_cache
@require_safe
def booking_detail(request, reference):
    booking = get_object_or_404(
        Reservation.objects.select_related("screening__film", "screening__room").prefetch_related("tickets"),
        reference=reference, customer=request.user,
    )
    return render(request, "booking_detail.html", {"booking": booking, "payment_location": PAYMENT_LOCATION})


@login_required
@never_cache
@require_safe
def my_bookings(request):
    bookings = Reservation.objects.filter(customer=request.user).select_related("screening__film")
    return render(request, "my_bookings.html", {"bookings": bookings})


@login_required
@never_cache
@require_safe
def download_ticket(request, reference):
    queryset = Ticket.objects.select_related("reservation__screening__film", "reservation__screening__room")
    if not has_role(request.user, GUICHET):
        queryset = queryset.filter(reservation__customer=request.user)
    ticket = get_object_or_404(queryset, reference=reference)
    return FileResponse(ticket_pdf(ticket), as_attachment=True, filename=f"billet-{ticket.reference}.pdf")
