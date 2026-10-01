from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.AlertListView.as_view(), name="alerts"),
    path("new/", views.CreateAlertView.as_view(), name="create"),
    path("<int:pk>/delete/", views.DeleteAlertView.as_view(), name="delete"),
    path("unsubscribe/<str:token>/", views.UnsubscribeView.as_view(), name="unsubscribe"),
]
