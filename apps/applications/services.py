"""Application workflow rules.

All state changes go through this module so the transition rules, the audit
trail and the domain events can never get out of sync.
"""

from __future__ import annotations

from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction

from apps.candidates.models import CandidateProfile
from apps.jobs.models import Job

from .models import Application, ApplicationEvent
from .signals import application_status_changed, application_submitted


class ApplicationError(Exception):
    """A workflow rule was violated. The message is safe to show to users."""


@transaction.atomic
def submit_application(*, candidate, job: Job, cover_letter: str = "", resume=None) -> Application:
    if not job.is_open:
        raise ApplicationError("This job is no longer accepting applications.")

    if resume is None:
        profile = CandidateProfile.objects.filter(user=candidate).first()
        if not profile or not profile.resume:
            raise ApplicationError("Please upload a resume to apply.")
        # Snapshot the profile resume so later profile edits don't change what was sent.
        with profile.resume.open("rb") as source:
            resume = ContentFile(source.read(), name="resume.pdf")

    application = Application(job=job, candidate=candidate, cover_letter=cover_letter)
    application.resume.save("resume.pdf", resume, save=False)
    try:
        with transaction.atomic():
            application.save()
    except IntegrityError:
        application.resume.delete(save=False)
        raise ApplicationError("You have already applied to this job.") from None

    ApplicationEvent.objects.create(
        application=application, actor=candidate, to_status=Application.Status.APPLIED
    )
    transaction.on_commit(
        lambda: application_submitted.send(sender=Application, application=application)
    )
    return application


@transaction.atomic
def change_status(*, application: Application, actor, to_status: str, note: str = "") -> None:
    application = Application.objects.select_for_update().get(pk=application.pk)
    from_status = application.status
    is_employer = application.job.company.owner_id == actor.pk
    is_candidate = application.candidate_id == actor.pk

    if is_candidate and not is_employer:
        allowed = {Application.Status.WITHDRAWN} if application.is_active else set()
    elif is_employer:
        allowed = Application.TRANSITIONS[from_status]
    else:
        raise ApplicationError("You cannot change this application.")

    if to_status not in allowed:
        raise ApplicationError(f"Cannot move an application from {from_status} to {to_status}.")

    application.status = to_status
    application.save(update_fields=["status", "updated_at"])
    ApplicationEvent.objects.create(
        application=application,
        actor=actor,
        from_status=from_status,
        to_status=to_status,
        note=note,
    )
    transaction.on_commit(
        lambda: application_status_changed.send(
            sender=Application,
            application=application,
            from_status=from_status,
            to_status=to_status,
        )
    )


def add_note(*, application: Application, actor, note: str) -> ApplicationEvent:
    if application.job.company.owner_id != actor.pk:
        raise ApplicationError("Only the employer can add notes.")
    return ApplicationEvent.objects.create(
        application=application, actor=actor, note=note, is_internal=True
    )
