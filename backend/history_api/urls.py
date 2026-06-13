from django.urls import URLPattern, path

from history_api import views

urlpatterns: list[URLPattern] = [
    path("history/sync", views.history_sync, name="history-sync"),
    path("sessions", views.session_list, name="session-list"),
    path("sessions/<str:session_id>", views.session_detail, name="session-detail"),
]
