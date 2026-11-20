from django.http import HttpResponse
from django.urls import path


def health(request):
    return HttpResponse("ok", content_type="text/plain")


urlpatterns = [path("healthz/", health)]
