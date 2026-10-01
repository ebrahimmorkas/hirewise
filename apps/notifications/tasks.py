import logging
from datetime import timedelta
from smtplib import SMTPException

from celery import shared_task
from django.utils import timezone

from apps.applications.models import Application
from apps.jobs.filters import JobFilter
from apps.jobs.models import Job

from .emails import absolute, send
from .models import JobAlert

logger = logging.getLogger(__name__)

RETRY = {
    "autoretry_for": (SMTPException, ConnectionError),
    "retry_backoff": True,
    "retry_kwargs": {"max_retries": 5},
}

MAX_JOBS_PER_DIGEST = 10
FREQUENCY_WINDOW = {
    JobAlert.Frequency.DAILY: timedelta(days=1),
    JobAlert.Frequency.WEEKLY: timedelta(days=7),
}


def _application(pk: int) -> Application | None:
    return (
        Application.objects.select_related("job__company__owner", "candidate").filter(pk=pk).first()
    )


@shared_task(**RETRY)
def notify_employer_of_application(application_id: int) -> None:
    application = _application(application_id)
    if application is None:
        return
    job = application.job
    send(
        "new_application",
        f"New applicant for {job.title}: {application.candidate.full_name}",
        job.company.owner.email,
        {"application": application, "url": absolute(application.get_absolute_url())},
    )


@shared_task(**RETRY)
def notify_status_change(application_id: int, from_status: str, to_status: str) -> None:
    application = _application(application_id)
    if application is None:
        return
    url = absolute(application.get_absolute_url())
    if to_status == Application.Status.WITHDRAWN:
        send(
            "application_withdrawn",
            f"{application.candidate.full_name} withdrew from {application.job.title}",
            application.job.company.owner.email,
            {"application": application, "url": url},
        )
        return

    latest_message = (
        application.events.filter(to_status=to_status, is_internal=False)
        .exclude(note="")
        .values_list("note", flat=True)
        .last()
    )
    send(
        "status_changed",
        f"Update on your application to {application.job.company.name}",
        application.candidate.email,
        {"application": application, "message": latest_message, "url": url},
    )


def matching_jobs(alert: JobAlert, since):
    base = Job.objects.published().filter(published_at__gt=since).select_related("company")
    return JobFilter(alert.params, queryset=base).qs[:MAX_JOBS_PER_DIGEST]


@shared_task
def send_job_alerts() -> int:
    """Send one digest per due alert containing jobs published since the last digest."""
    now = timezone.now()
    sent = 0
    alerts = JobAlert.objects.filter(is_active=True).select_related("candidate")
    for alert in alerts:
        window = FREQUENCY_WINDOW[alert.frequency]
        if alert.last_sent_at and now - alert.last_sent_at < window:
            continue
        since = alert.last_sent_at or alert.created_at
        jobs = list(matching_jobs(alert, since))

        # Claim the alert before sending so concurrent runs never double-send.
        claimed = JobAlert.objects.filter(pk=alert.pk, last_sent_at=alert.last_sent_at).update(
            last_sent_at=now
        )
        if not claimed or not jobs:
            continue

        unsubscribe = alert.unsubscribe_url()
        send(
            "job_alert",
            f'{len(jobs)} new job{"s" if len(jobs) != 1 else ""} for "{alert.name}"',
            alert.candidate.email,
            {
                "alert": alert,
                "jobs": [(job, absolute(job.get_absolute_url())) for job in jobs],
                "unsubscribe_url": unsubscribe,
            },
            headers={"List-Unsubscribe": f"<{unsubscribe}>"},
        )
        sent += 1
    logger.info("Sent %d job alert digests", sent)
    return sent
