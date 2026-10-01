from django.urls import path

from . import views

app_name = "candidates"

urlpatterns = [
    path("profile/", views.ProfileUpdateView.as_view(), name="profile"),
]
