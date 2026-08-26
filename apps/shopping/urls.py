from __future__ import annotations

from django.urls import path

from apps.shopping.views import cart_add
from apps.shopping.views import cart_apply_coupon
from apps.shopping.views import cart_detail
from apps.shopping.views import cart_remove
from apps.shopping.views import cart_update

app_name = "shopping"

urlpatterns = [
    path("", cart_detail, name="cart"),
    path("add/", cart_add, name="add"),
    path("update/<uuid:item_id>/", cart_update, name="update"),
    path("remove/<uuid:item_id>/", cart_remove, name="remove"),
    path("coupon/", cart_apply_coupon, name="apply_coupon"),
]
