from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, FormView, ListView

from apps.accounts.mixins import CandidateRequiredMixin, EmployerRequiredMixin
from apps.candidates.models import CandidateProfile
from apps.jobs.models import Job

from . import services
from .forms import ApplyForm, NoteForm
from .models import Application


class ApplyView(CandidateRequiredMixin, FormView):
    form_class = ApplyForm
    template_name = "applications/apply.html"

    def dispatch(self, request, *args, **kwargs):
        self.job = get_object_or_404(Job.objects.select_related("company"), slug=kwargs["slug"])
        if request.user.is_authenticated:
            existing = Application.objects.filter(job=self.job, candidate=request.user).first()
            if existing:
                messages.info(request, "You have already applied to this job.")
                return redirect(existing)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        profile = CandidateProfile.objects.filter(user=self.request.user).first()
        kwargs["has_profile_resume"] = bool(profile and profile.resume)
        return kwargs

    def get_context_data(self, **kwargs):
        return super().get_context_data(job=self.job, **kwargs)

    def form_valid(self, form):
        try:
            application = services.submit_application(
                candidate=self.request.user,
                job=self.job,
                cover_letter=form.cleaned_data["cover_letter"],
                resume=form.cleaned_data.get("resume"),
            )
        except services.ApplicationError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        messages.success(self.request, f"Application sent to {self.job.company.name}. Good luck!")
        return redirect(application)


class ApplicationAccessMixin(LoginRequiredMixin):
    """Applications are visible to the candidate who applied and the hiring employer."""

    def get_queryset(self):
        user = self.request.user
        return Application.objects.filter(
            Q(candidate=user) | Q(job__company__owner=user)
        ).select_related("job__company", "candidate")


class MyApplicationsView(CandidateRequiredMixin, ListView):
    template_name = "applications/my_applications.html"
    context_object_name = "applications"

    def get_queryset(self):
        return Application.objects.filter(candidate=self.request.user).select_related(
            "job__company"
        )


class ApplicationDetailView(ApplicationAccessMixin, DetailView):
    template_name = "applications/detail.html"
    context_object_name = "application"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        application = self.object
        is_employer = application.job.company.owner_id == self.request.user.pk
        events = application.events.select_related("actor")
        if not is_employer:
            events = events.filter(is_internal=False)
        context.update(
            is_employer=is_employer,
            events=events,
            note_form=NoteForm(),
            profile=CandidateProfile.objects.filter(user=application.candidate).first(),
        )
        return context


class ResumeDownloadView(ApplicationAccessMixin, View):
    """Serve resumes through an access-checked view instead of public media URLs."""

    def get(self, request, pk):
        application = get_object_or_404(self.get_queryset(), pk=pk)
        filename = f"{application.candidate.full_name or 'resume'}.pdf".replace('"', "")
        return FileResponse(application.resume.open("rb"), as_attachment=True, filename=filename)


class ChangeStatusView(ApplicationAccessMixin, View):
    def post(self, request, pk):
        application = get_object_or_404(self.get_queryset(), pk=pk)
        try:
            services.change_status(
                application=application,
                actor=request.user,
                to_status=request.POST.get("status", ""),
                note=request.POST.get("note", ""),
            )
        except services.ApplicationError as exc:
            if request.headers.get("HX-Request"):
                raise PermissionDenied(str(exc)) from exc
            messages.error(request, str(exc))
            return redirect(application)

        if request.headers.get("HX-Request") and request.POST.get("from") == "board":
            return render(request, "applications/_board.html", board_context(application.job))
        messages.success(request, "Application updated.")
        if application.candidate_id == request.user.pk:
            return redirect("applications:mine")
        return redirect(application)


class AddNoteView(ApplicationAccessMixin, View):
    def post(self, request, pk):
        application = get_object_or_404(self.get_queryset(), pk=pk)
        form = NoteForm(request.POST)
        if form.is_valid():
            try:
                services.add_note(
                    application=application, actor=request.user, note=form.cleaned_data["note"]
                )
            except services.ApplicationError as exc:
                raise PermissionDenied(str(exc)) from exc
        return redirect(application)


def board_context(job: Job) -> dict:
    applications = list(job.applications.select_related("candidate").order_by("created_at"))
    columns = [
        {
            "status": status,
            "label": Application.Status(status).label,
            "items": [a for a in applications if a.status == status],
        }
        for status in Application.PIPELINE
    ]
    rejected = [a for a in applications if a.status in {"rejected", "withdrawn"}]
    return {"job": job, "columns": columns, "rejected": rejected}


class PipelineView(EmployerRequiredMixin, View):
    def get(self, request, slug):
        job = get_object_or_404(Job, slug=slug, company__owner=request.user)
        return render(request, "applications/pipeline.html", board_context(job))
