from django.urls import path

from . import views

app_name = "applications"

urlpatterns = [
    path("", views.MyApplicationsView.as_view(), name="mine"),
    path("<int:pk>/", views.ApplicationDetailView.as_view(), name="detail"),
    path("<int:pk>/resume/", views.ResumeDownloadView.as_view(), name="resume"),
    path("<int:pk>/status/", views.ChangeStatusView.as_view(), name="status"),
    path("<int:pk>/notes/", views.AddNoteView.as_view(), name="note"),
    path("apply/<slug:slug>/", views.ApplyView.as_view(), name="apply"),
    path("pipeline/<slug:slug>/", views.PipelineView.as_view(), name="pipeline"),
]
