from __future__ import annotations

from django.urls import path

from apps.catalogue.views import catalogue_index
from apps.catalogue.views import category_detail

app_name = "catalogue"

urlpatterns = [
    path("", catalogue_index, name="index"),
    path("<slug:slug>/", category_detail, name="category"),
]
