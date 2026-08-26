from django.urls import path

from apps.catalogue.views import attribute_definition_detail

app_name = "catalogue.admin"

urlpatterns = [
    path(
        "attribute-definition/<uuid:pk>/",
        attribute_definition_detail,
        name="attribute_definition_detail",
    ),
]
