from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, TemplateView, UpdateView

from apps.accounts.mixins import EmployerRequiredMixin

from .analytics import company_analytics
from .forms import CompanyForm
from .models import Company


class CompanyCreateView(EmployerRequiredMixin, CreateView):
    model = Company
    form_class = CompanyForm
    template_name = "companies/form.html"
    success_url = reverse_lazy("jobs:dashboard")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and hasattr(request.user, "company"):
            return redirect("companies:edit")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.owner = self.request.user
        messages.success(self.request, "Company profile created. Now post your first job!")
        return super().form_valid(form)


class CompanyUpdateView(EmployerRequiredMixin, UpdateView):
    model = Company
    form_class = CompanyForm
    template_name = "companies/form.html"
    success_url = reverse_lazy("jobs:dashboard")

    def get_object(self, queryset=None):
        return self.request.user.company

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if user.is_authenticated and user.is_employer and not hasattr(user, "company"):
            return redirect("companies:create")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Company profile updated.")
        return super().form_valid(form)


class CompanyDetailView(DetailView):
    model = Company
    template_name = "companies/detail.html"
    context_object_name = "company"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["jobs"] = (
            self.object.jobs.published().prefetch_related("skills").order_by("-published_at")
        )
        return context


class AnalyticsView(EmployerRequiredMixin, TemplateView):
    template_name = "companies/analytics.html"

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if user.is_authenticated and user.is_employer and not hasattr(user, "company"):
            return redirect("companies:create")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        return super().get_context_data(stats=company_analytics(self.request.user.company))
