from django.contrib.auth import views as auth_views
from django.http import HttpResponse
from django.urls import path

from cinema import programme, spectator
from cinema.api import api


def health(request):
    return HttpResponse("ok", content_type="text/plain")


urlpatterns = [
    path("", programme.programme, name="programme"),
    path("healthz/", health),
    path("connexion/", auth_views.LoginView.as_view(), name="login"),
    path("deconnexion/", auth_views.LogoutView.as_view(), name="logout"),
    path("inscription/", spectator.signup, name="signup"),
    path("seances/<int:screening_id>/reserver/", spectator.book, name="book"),
    path("mes-reservations/", spectator.my_bookings, name="my_bookings"),
    path("mes-reservations/<uuid:reference>/", spectator.booking_detail, name="booking_detail"),
    path("billets/<uuid:reference>/", spectator.download_ticket, name="download_ticket"),
    path("api/", api.urls),
]
