from django.urls import path

from . import views

app_name = "jobs"

urlpatterns = [
    path("employer/", views.EmployerDashboardView.as_view(), name="dashboard"),
    path("employer/new/", views.JobCreateView.as_view(), name="create"),
    path("employer/<slug:slug>/edit/", views.JobUpdateView.as_view(), name="edit"),
    path(
        "employer/<slug:slug>/<str:action>/",
        views.JobStatusView.as_view(),
        name="status",
    ),
    path("<slug:slug>/", views.JobDetailView.as_view(), name="detail"),
]
