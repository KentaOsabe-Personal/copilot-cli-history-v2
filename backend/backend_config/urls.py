from django.urls import URLPattern, URLResolver, path

from health.views import up

urlpatterns: list[URLPattern | URLResolver] = [
    path("up", up, name="up"),
]
