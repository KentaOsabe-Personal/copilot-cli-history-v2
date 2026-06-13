from django.urls import URLPattern, URLResolver, include, path

from health.views import up

urlpatterns: list[URLPattern | URLResolver] = [
    path("up", up, name="up"),
    path("api/", include("history_api.urls")),
]
