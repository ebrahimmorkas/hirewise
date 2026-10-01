from django.contrib import messages
from django.db.models import F
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.accounts.mixins import EmployerRequiredMixin

from .forms import JobForm
from .models import Job


class CompanyRequiredMixin(EmployerRequiredMixin):
    """Employers must create a company profile before managing jobs."""

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if user.is_authenticated and user.is_employer and not hasattr(user, "company"):
            messages.info(request, "Set up your company profile first.")
            return redirect("companies:create")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Job.objects.filter(company=self.request.user.company)


class EmployerDashboardView(CompanyRequiredMixin, ListView):
    template_name = "jobs/dashboard.html"
    context_object_name = "jobs"

    def get_queryset(self):
        return super().get_queryset().order_by("-created_at")


class JobCreateView(CompanyRequiredMixin, CreateView):
    model = Job
    form_class = JobForm
    template_name = "jobs/form.html"

    def form_valid(self, form):
        form.instance.company = self.request.user.company
        response = super().form_valid(form)
        if "publish" in self.request.POST:
            self.object.publish()
            messages.success(self.request, "Job published.")
        else:
            messages.success(self.request, "Draft saved.")
        return response

    def get_success_url(self):
        return self.object.get_absolute_url()


class JobUpdateView(CompanyRequiredMixin, UpdateView):
    model = Job
    form_class = JobForm
    template_name = "jobs/form.html"

    def form_valid(self, form):
        messages.success(self.request, "Job updated.")
        return super().form_valid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()


class JobStatusView(CompanyRequiredMixin, View):
    """POST-only endpoint to publish or close a job."""

    def post(self, request, slug, action):
        job = get_object_or_404(self.get_queryset(), slug=slug)
        if action == "publish" and job.status != Job.Status.PUBLISHED:
            job.publish()
            messages.success(request, f"'{job.title}' is now live.")
        elif action == "close" and job.status == Job.Status.PUBLISHED:
            job.close()
            messages.info(request, f"'{job.title}' is closed to new applications.")
        return redirect("jobs:dashboard")


class JobDetailView(DetailView):
    template_name = "jobs/detail.html"
    context_object_name = "job"

    def get_queryset(self):
        return Job.objects.select_related("company").prefetch_related("skills")

    def get_object(self, queryset=None):
        job = super().get_object(queryset)
        user = self.request.user
        is_owner = user.is_authenticated and job.company.owner_id == user.pk
        if not job.is_open and not is_owner and job.status != Job.Status.CLOSED:
            raise Http404("Job not found")
        if not is_owner:
            # Atomic increment: no lost updates under concurrent views.
            Job.objects.filter(pk=job.pk).update(view_count=F("view_count") + 1)
        self.is_owner = is_owner
        return job

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_owner"] = self.is_owner
        return context
