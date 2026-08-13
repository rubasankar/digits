from typing import TYPE_CHECKING

from django.shortcuts import render

if TYPE_CHECKING:
    from django.http import HttpRequest
    from django.http import HttpResponse


def home(request: HttpRequest) -> HttpResponse:
    return render(request, "home.html")
