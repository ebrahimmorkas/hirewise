from django.urls import path

from . import views

app_name = "companies"

urlpatterns = [
    path("new/", views.CompanyCreateView.as_view(), name="create"),
    path("edit/", views.CompanyUpdateView.as_view(), name="edit"),
    path("<slug:slug>/", views.CompanyDetailView.as_view(), name="detail"),
]
