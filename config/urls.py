from django.http import HttpResponse
from django.urls import path

from cinema import programme


def health(request):
    return HttpResponse("ok", content_type="text/plain")


urlpatterns = [
    path("", programme.programme, name="programme"),
    path("healthz/", health),
]
