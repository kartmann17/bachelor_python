from django.contrib import messages
from django.core import signing
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_http_methods, require_safe

from .access import PROGRAMMATION, requires_role
from .models import Screening
from .programme import selected_date
from .reservations import BookingError
from .scheduling import create_draft, publish, schedule_impact, snapshot, update_screening
from .web_forms import ScreeningForm


@requires_role(PROGRAMMATION)
@never_cache
@require_safe
def schedule(request):
    day = selected_date(request)
    screenings = Screening.objects.select_related("film", "room").filter(starts_at__date=day)
    return render(request, "schedule.html", {"screenings": screenings, "day": day})


@requires_role(PROGRAMMATION)
@never_cache
@require_http_methods(["GET", "HEAD", "POST"])
def schedule_create(request):
    form = ScreeningForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            screening = create_draft(form.cleaned_data)
            messages.success(request, "Brouillon créé. Publiez-le pour l’afficher dans le programme public.")
            return redirect(f"{reverse('schedule')}?date={screening.starts_at_local_date}")
        except BookingError as exc:
            form.add_error(None, str(exc))
    return render(request, "staff_form.html", {
        "title": "Nouvelle séance", "form": form, "submit": "Créer le brouillon",
    }, status=400 if form.errors else 200)


@requires_role(PROGRAMMATION)
@never_cache
@require_POST
def schedule_publish(request, screening_id):
    screening = get_object_or_404(Screening, pk=screening_id)
    try:
        publish(screening_id)
        messages.success(request, "Séance publiée dans le programme.")
    except BookingError as exc:
        messages.error(request, str(exc))
    return redirect(f"{reverse('schedule')}?date={screening.starts_at_local_date}")


@requires_role(PROGRAMMATION)
@never_cache
@require_http_methods(["GET", "HEAD", "POST"])
def schedule_edit(request, screening_id):
    screening = get_object_or_404(Screening.objects.select_related("film", "room"), pk=screening_id)
    if screening.status == Screening.Status.CANCELLED or not screening.future:
        raise Http404("Cette séance ne peut plus être modifiée.")
    form = ScreeningForm(request.POST if request.method == "POST" else None, instance=screening)
    impact = schedule_impact(screening)
    confirmation = None
    status = 200
    if request.method == "POST":
        if form.is_valid():
            values = snapshot(form.cleaned_data)
            token = request.POST.get("confirmation")
            if token:
                try:
                    approved = signing.loads(token, salt="cinema.schedule", max_age=900)
                    if approved["screening"] != screening_id or approved["values"] != values:
                        raise signing.BadSignature
                    updated = update_screening(
                        screening_id, form.cleaned_data, request.user, approved["revision"], approved["impact"],
                    )
                    messages.success(request, "Séance modifiée. Le changement a été journalisé.")
                    return redirect(f"{reverse('schedule')}?date={updated.starts_at_local_date}")
                except signing.BadSignature:
                    form.add_error(None, "La confirmation est périmée. Vérifiez à nouveau la modification.")
                    status = 409
                except BookingError as exc:
                    form.add_error(None, str(exc))
                    status = exc.status
            else:
                confirmation = signing.dumps({
                    "screening": screening_id, "revision": screening.revision, "values": values,
                    "impact": impact,
                }, salt="cinema.schedule")
        else:
            status = 400
    return render(request, "schedule_edit.html", {
        "form": form, "screening": screening, "impact": impact,
        "confirmation": confirmation, "history": screening.changes.select_related("actor")[:10],
    }, status=status)
