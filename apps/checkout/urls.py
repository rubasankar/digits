from __future__ import annotations

from django.urls import path

from apps.checkout.views import checkout_address
from apps.checkout.views import checkout_edit_address
from apps.checkout.views import checkout_payment
from apps.checkout.views import checkout_review
from apps.checkout.views import checkout_shipping
from apps.checkout.views import checkout_start

app_name = "checkout"

urlpatterns = [
    path("", checkout_start, name="start"),
    path("address/", checkout_address, name="address"),
    path("address/<uuid:pk>/edit/", checkout_edit_address, name="edit_address"),
    path("shipping/", checkout_shipping, name="shipping"),
    path("payment/", checkout_payment, name="payment"),
    path("review/", checkout_review, name="review"),
]
