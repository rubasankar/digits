"""
URL configuration
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include
from django.urls import path
from django.views import defaults as default_views
from labb.shortcuts import set_theme_view

handler400 = "core.views.handler_400"
handler403 = "core.views.handler_403"
handler404 = "core.views.handler_404"
handler500 = "core.views.handler_500"

urlpatterns = [
    path("auth/", include("allauth.urls")),
    path("set-theme/", set_theme_view, name="set_theme"),
    path("admin/catalogue-api/", include("apps.catalogue.urls.admin")),
    path("admin/", admin.site.urls),
    path("catalogue/", include("apps.catalogue.urls.catalogue")),
    path("products/", include("apps.catalogue.urls.product")),
    path("cart/", include("apps.shopping.urls")),
    path("checkout/", include("apps.checkout.urls")),
    path("orders/", include("apps.orders.urls")),
    path("account/", include("apps.customers.urls")),
    path("", include("core.urls")),
    *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),
]


if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += [
        path(
            "400/",
            default_views.bad_request,
            kwargs={"exception": Exception("Bad Request!")},
        ),
        path(
            "403/",
            default_views.permission_denied,
            kwargs={"exception": Exception("Permission Denied")},
        ),
        path(
            "404/",
            default_views.page_not_found,
            kwargs={"exception": Exception("Page not Found")},
        ),
        path("500/", default_views.server_error),
    ]
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns = [path("__debug__/", include(debug_toolbar.urls)), *urlpatterns]
