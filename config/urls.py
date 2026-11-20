from django.contrib.auth import views as auth_views
from django.http import HttpResponse
from django.urls import path

from cinema import management_views, programme, reporting, spectator, staff
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
    path("gestion/", staff.workspace, name="workspace"),
    path("gestion/guichet/", staff.desk_sale, name="desk_sale"),
    path("gestion/guichet/rechercher/", staff.desk_lookup, name="desk_lookup"),
    path("gestion/guichet/<uuid:reference>/regler/", staff.desk_pay, name="desk_pay"),
    path("gestion/guichet/<uuid:reference>/", staff.desk_receipt, name="desk_receipt"),
    path("gestion/controle/", staff.check_in, name="check_in"),
    path("gestion/programmation/", management_views.schedule, name="schedule"),
    path("gestion/programmation/nouvelle/", management_views.schedule_create, name="schedule_create"),
    path("gestion/programmation/<int:screening_id>/publier/", management_views.schedule_publish, name="schedule_publish"),
    path("gestion/programmation/<int:screening_id>/modifier/", management_views.schedule_edit, name="schedule_edit"),
    path("gestion/remplissage/", reporting.dashboard, name="dashboard"),
    path("gestion/guichet/<uuid:reference>/annuler/", staff.desk_cancel, name="desk_cancel"),
    path("api/", api.urls),
]
