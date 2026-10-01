from datetime import timedelta

import pytest
from django.core import mail
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.accounts.tests.factories import CandidateFactory
from apps.applications.services import change_status, submit_application
from apps.applications.tests.factories import ApplicationFactory
from apps.applications.tests.test_services import resume_upload
from apps.jobs.models import Job
from apps.jobs.tests.factories import JobFactory
from apps.notifications.models import JobAlert
from apps.notifications.tasks import send_job_alerts
from apps.notifications.views import search_params

pytestmark = pytest.mark.django_db


# --- application emails --------------------------------------------------------------


def test_employer_is_emailed_on_new_application(django_capture_on_commit_callbacks):
    job = JobFactory(title="Data Engineer")
    candidate = CandidateFactory(full_name="Ada Lovelace")

    with django_capture_on_commit_callbacks(execute=True):
        submit_application(candidate=candidate, job=job, resume=resume_upload())

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [job.company.owner.email]
    assert mail.outbox[0].subject == "New applicant for Data Engineer: Ada Lovelace"


def test_candidate_gets_status_update_with_employer_message(django_capture_on_commit_callbacks):
    application = ApplicationFactory()

    with django_capture_on_commit_callbacks(execute=True):
        change_status(
            application=application,
            actor=application.job.company.owner,
            to_status="interview",
            note="Are you free Tuesday at 10am?",
        )

    message = mail.outbox[0]
    assert message.to == [application.candidate.email]
    assert "would like to interview you" in message.body
    assert "Are you free Tuesday at 10am?" in message.body


def test_withdrawal_notifies_employer(django_capture_on_commit_callbacks):
    application = ApplicationFactory()

    with django_capture_on_commit_callbacks(execute=True):
        change_status(application=application, actor=application.candidate, to_status="withdrawn")

    assert mail.outbox[0].to == [application.job.company.owner.email]
    assert "withdrew" in mail.outbox[0].subject


# --- job alerts -----------------------------------------------------------------------


def make_alert(params, **kwargs):
    alert = JobAlert.objects.create(
        candidate=kwargs.pop("candidate", None) or CandidateFactory(),
        name="Remote Python",
        params=params,
        **kwargs,
    )
    JobAlert.objects.filter(pk=alert.pk).update(created_at=timezone.now() - timedelta(days=2))
    alert.refresh_from_db()
    return alert


def test_search_params_parsing():
    params = search_params("q=python&workplace=remote&workplace=hybrid&page=3&location=")

    assert params == {"q": "python", "workplace": ["remote", "hybrid"]}


def test_alert_digest_contains_only_matching_new_jobs():
    alert = make_alert({"q": "python", "workplace": ["remote"]})
    JobFactory(title="Python Developer", workplace=Job.Workplace.REMOTE, location="")
    JobFactory(title="Python Developer (Onsite)", workplace=Job.Workplace.ONSITE)
    JobFactory(
        title="Old Python role",
        workplace=Job.Workplace.REMOTE,
        published_at=timezone.now() - timedelta(days=5),
    )

    assert send_job_alerts() == 1

    body = mail.outbox[0].body
    assert "Python Developer at" in body
    assert "Onsite" not in body and "Old Python role" not in body
    assert alert.unsubscribe_url() in body
    assert mail.outbox[0].extra_headers["List-Unsubscribe"] == f"<{alert.unsubscribe_url()}>"


def test_alert_not_resent_within_its_window():
    make_alert({"q": "python"})
    JobFactory(title="Python Developer")

    assert send_job_alerts() == 1
    JobFactory(title="Python Engineer")
    assert send_job_alerts() == 0  # daily alert already sent


def test_no_email_when_nothing_matches():
    alert = make_alert({"q": "cobol"})
    JobFactory(title="Python Developer")

    assert send_job_alerts() == 0
    assert mail.outbox == []
    alert.refresh_from_db()
    assert alert.last_sent_at is not None  # window advances anyway


def test_inactive_alerts_are_skipped():
    make_alert({}, is_active=False)
    JobFactory()

    assert send_job_alerts() == 0


def test_management_command(capsys):
    make_alert({})
    JobFactory()

    call_command("send_job_alerts")

    assert "Sent 1 job alert digest(s)." in capsys.readouterr().out


def test_create_alert_from_search(client):
    candidate = CandidateFactory()
    client.force_login(candidate)

    response = client.post(
        reverse("notifications:create"),
        {"query": "q=django&level=senior&page=2", "frequency": "weekly"},
    )

    alert = candidate.job_alerts.get()
    assert response.url == reverse("notifications:alerts")
    assert alert.params == {"q": "django", "level": ["senior"]}
    assert alert.frequency == "weekly"
    assert alert.name == "django · senior"


def test_unsubscribe_with_signed_token(client):
    alert = make_alert({})
    url = reverse("notifications:unsubscribe", args=[alert.unsubscribe_token()])

    assert client.get(url).status_code == 200
    client.post(url)

    alert.refresh_from_db()
    assert not alert.is_active


def test_tampered_unsubscribe_token_is_rejected(client):
    alert = make_alert({})
    token = alert.unsubscribe_token()[:-2] + "xx"

    response = client.post(reverse("notifications:unsubscribe", args=[token]))

    assert b"Link not valid" in response.content
    alert.refresh_from_db()
    assert alert.is_active
