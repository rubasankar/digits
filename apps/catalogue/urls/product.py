from __future__ import annotations

from django.urls import path

from apps.catalogue.views import product_detail

app_name = "products"

urlpatterns = [
    path("<slug:slug>/", product_detail, name="detail"),
]
