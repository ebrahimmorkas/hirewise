from django.urls import path

from . import views

app_name = "jobs"

urlpatterns = [
    path("", views.JobListView.as_view(), name="list"),
    path("saved/", views.SavedJobsView.as_view(), name="saved"),
    path("for-you/", views.RecommendedJobsView.as_view(), name="recommended"),
    path("employer/", views.EmployerDashboardView.as_view(), name="dashboard"),
    path("employer/new/", views.JobCreateView.as_view(), name="create"),
    path("employer/<slug:slug>/edit/", views.JobUpdateView.as_view(), name="edit"),
    path(
        "employer/<slug:slug>/<str:action>/",
        views.JobStatusView.as_view(),
        name="status",
    ),
    path("<slug:slug>/", views.JobDetailView.as_view(), name="detail"),
    path("<slug:slug>/save/", views.ToggleSaveJobView.as_view(), name="save"),
]
