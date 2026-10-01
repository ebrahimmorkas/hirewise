from django.contrib import messages
from django.http import QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import ListView

from apps.accounts.mixins import CandidateRequiredMixin
from apps.jobs.filters import JobFilter

from .models import JobAlert

IGNORED_PARAMS = {"page", "sort", "csrfmiddlewaretoken"}
MULTI_VALUE_PARAMS = {"workplace", "level", "employment_type", "skills"}


def search_params(querystring: str) -> dict:
    """Turn a job-search querystring into JSON-serialisable alert params."""
    query = QueryDict(querystring)
    params = {}
    for key in query:
        values = [v for v in query.getlist(key) if v]
        if key in IGNORED_PARAMS or not values:
            continue
        params[key] = values if key in MULTI_VALUE_PARAMS else values[-1]
    return params


def describe(params: dict) -> str:
    parts = []
    if params.get("q"):
        parts.append(params["q"])
    if params.get("location"):
        parts.append(f"in {params['location']}")
    for key in ("workplace", "level", "employment_type"):
        if params.get(key):
            parts.append(", ".join(params[key]))
    return " · ".join(parts) or "All new jobs"


class CreateAlertView(CandidateRequiredMixin, View):
    """Save the current search (posted as the querystring) as an email alert."""

    def post(self, request):
        params = search_params(request.POST.get("query", ""))
        if not JobFilter(params).is_valid():
            messages.error(request, "That search can't be saved as an alert.")
            return redirect("jobs:list")
        frequency = request.POST.get("frequency")
        if frequency not in JobAlert.Frequency.values:
            frequency = JobAlert.Frequency.DAILY
        JobAlert.objects.create(
            candidate=request.user,
            name=describe(params)[:120],
            params=params,
            frequency=frequency,
        )
        messages.success(request, "Job alert created. We'll email you when new jobs match.")
        return redirect("notifications:alerts")


class AlertListView(CandidateRequiredMixin, ListView):
    template_name = "notifications/alerts.html"
    context_object_name = "alerts"

    def get_queryset(self):
        return self.request.user.job_alerts.all()


class DeleteAlertView(CandidateRequiredMixin, View):
    def post(self, request, pk):
        get_object_or_404(JobAlert, pk=pk, candidate=request.user).delete()
        messages.info(request, "Alert deleted.")
        return redirect("notifications:alerts")


class UnsubscribeView(View):
    """One-click unsubscribe from an email link. No login required: the token is signed."""

    def get(self, request, token):
        alert = JobAlert.from_token(token)
        return render(request, "notifications/unsubscribe.html", {"alert": alert})

    def post(self, request, token):
        alert = JobAlert.from_token(token)
        if alert:
            alert.is_active = False
            alert.save(update_fields=["is_active", "updated_at"])
        return render(request, "notifications/unsubscribe.html", {"alert": alert, "done": True})
