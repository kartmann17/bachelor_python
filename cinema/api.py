from decimal import Decimal
from uuid import UUID

from django.views.decorators.cache import never_cache
from ninja import Field, NinjaAPI, Schema
from ninja.security import django_auth

from .reservations import MAX_PLACES, BookingError, reserve

api = NinjaAPI(
    title="API du Grand Cinéma",
    version="1.0.0",
    description=(
        "Connectez-vous sur le site pour utiliser cette API. Une même clé de demande permet "
        "de reprendre une réservation sans débiter deux fois le stock."
    ),
    urls_namespace="api_cinema",
    docs_decorator=never_cache,
)


class BookingRequest(Schema):
    screening_id: int = Field(gt=0, description="Identifiant de la séance publiée.")
    quantity: int = Field(ge=1, le=MAX_PLACES, description="Nombre de places.")
    request_key: UUID = Field(description="UUID unique, à réutiliser en cas de nouvel envoi.")


class BookingResponse(Schema):
    reference: UUID
    screening_id: int
    status: str
    quantity: int
    total: Decimal


class ErrorResponse(Schema):
    detail: str


@api.post(
    "/reservations/",
    auth=django_auth,
    response={200: BookingResponse, 201: BookingResponse, 401: ErrorResponse, 403: ErrorResponse,
              404: ErrorResponse, 409: ErrorResponse},
    summary="Réserver des places en ligne",
)
def create_booking(request, body: BookingRequest):
    try:
        booking, created = reserve(user=request.user, **body.model_dump())
    except BookingError as exc:
        return exc.status, {"detail": str(exc)}
    return (201 if created else 200), booking
