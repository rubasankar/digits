from __future__ import annotations

from django.urls import path

from apps.orders.views import order_confirmation
from apps.orders.views import order_detail
from apps.orders.views import order_history
from apps.orders.views import return_request_create

app_name = "orders"

urlpatterns = [
    path("", order_history, name="history"),
    path("confirmation/<str:number>/", order_confirmation, name="confirmation"),
    path("<str:number>/return/", return_request_create, name="return_create"),
    path("<str:number>/", order_detail, name="detail"),
]
