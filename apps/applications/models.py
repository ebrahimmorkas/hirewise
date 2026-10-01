import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.core.models import TimeStampedModel
from apps.jobs.models import Job


def application_resume_path(instance, filename: str) -> str:
    return f"applications/{uuid.uuid4().hex}.pdf"


class Application(TimeStampedModel):
    class Status(models.TextChoices):
        APPLIED = "applied", "Applied"
        SCREENING = "screening", "Screening"
        INTERVIEW = "interview", "Interview"
        OFFER = "offer", "Offer"
        HIRED = "hired", "Hired"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"

    # Pipeline columns shown on the employer board, in order.
    PIPELINE = [Status.APPLIED, Status.SCREENING, Status.INTERVIEW, Status.OFFER, Status.HIRED]
    TERMINAL = {Status.HIRED, Status.REJECTED, Status.WITHDRAWN}

    # Allowed status transitions for employers. Candidates may only withdraw.
    TRANSITIONS = {
        Status.APPLIED: {Status.SCREENING, Status.INTERVIEW, Status.REJECTED},
        Status.SCREENING: {Status.INTERVIEW, Status.REJECTED},
        Status.INTERVIEW: {Status.OFFER, Status.REJECTED},
        Status.OFFER: {Status.HIRED, Status.REJECTED},
        Status.HIRED: set(),
        Status.REJECTED: set(),
        Status.WITHDRAWN: set(),
    }

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="applications")
    candidate = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="applications"
    )
    cover_letter = models.TextField(blank=True)
    resume = models.FileField(upload_to=application_resume_path)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.APPLIED)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["job", "candidate"], name="one_application_per_job"),
        ]
        indexes = [models.Index(fields=["job", "status"])]

    def __str__(self) -> str:
        return f"{self.candidate} → {self.job}"

    def get_absolute_url(self) -> str:
        return reverse("applications:detail", args=[self.pk])

    def allowed_transitions(self) -> list[str]:
        order = list(self.Status.values)
        return sorted(self.TRANSITIONS[self.status], key=order.index)

    @property
    def is_active(self) -> bool:
        return self.status not in self.TERMINAL


class ApplicationEvent(models.Model):
    """Audit trail of everything that happened to an application."""

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    from_status = models.CharField(max_length=12, blank=True)
    to_status = models.CharField(max_length=12, blank=True)
    note = models.TextField(blank=True)
    is_internal = models.BooleanField(
        default=False, help_text="Internal notes are only visible to the employer."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.application}: {self.from_status} → {self.to_status}"
