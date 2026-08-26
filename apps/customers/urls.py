from __future__ import annotations

from django.urls import path

from .views import account_dashboard
from .views import address_add
from .views import address_delete
from .views import address_edit
from .views import address_list
from .views import order_history
from .views import profile_detail
from .views import profile_edit
from .views import security_overview
from .views import wishlist_detail
from .views import wishlist_remove

app_name = "customers"

urlpatterns = [
    path("", account_dashboard, name="dashboard"),
    path("profile/", profile_detail, name="profile"),
    path("profile/edit/", profile_edit, name="profile_edit"),
    path("addresses/", address_list, name="addresses"),
    path("addresses/add/", address_add, name="address_add"),
    path("addresses/<uuid:pk>/edit/", address_edit, name="address_edit"),
    path("addresses/<uuid:pk>/delete/", address_delete, name="address_delete"),
    path("orders/", order_history, name="order_history"),
    path("wishlist/", wishlist_detail, name="wishlist"),
    path("wishlist/<uuid:pk>/remove/", wishlist_remove, name="wishlist_remove"),
    path("security/", security_overview, name="security"),
]
