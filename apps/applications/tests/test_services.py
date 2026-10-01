import pytest
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.tests.factories import CandidateFactory, EmployerFactory
from apps.applications.models import Application
from apps.applications.services import (
    ApplicationError,
    add_note,
    change_status,
    submit_application,
)
from apps.applications.signals import application_status_changed, application_submitted
from apps.applications.tests.factories import PDF_BYTES, ApplicationFactory
from apps.candidates.models import CandidateProfile
from apps.jobs.models import Job
from apps.jobs.tests.factories import JobFactory

pytestmark = pytest.mark.django_db

S = Application.Status


def resume_upload():
    return SimpleUploadedFile("cv.pdf", PDF_BYTES, content_type="application/pdf")


def test_submit_with_uploaded_resume_creates_application_and_event():
    candidate, job = CandidateFactory(), JobFactory()

    application = submit_application(candidate=candidate, job=job, resume=resume_upload())

    assert application.status == S.APPLIED
    assert application.resume.read() == PDF_BYTES
    assert list(application.events.values_list("to_status", flat=True)) == [S.APPLIED]


def test_submit_snapshots_profile_resume():
    candidate = CandidateFactory()
    profile = CandidateProfile.for_user(candidate)
    profile.resume.save("x.pdf", ContentFile(PDF_BYTES))

    application = submit_application(candidate=candidate, job=JobFactory())

    assert application.resume.name != profile.resume.name  # an independent copy
    assert application.resume.read() == PDF_BYTES


def test_submit_without_any_resume_fails():
    with pytest.raises(ApplicationError, match="upload a resume"):
        submit_application(candidate=CandidateFactory(), job=JobFactory())


def test_cannot_apply_twice():
    candidate, job = CandidateFactory(), JobFactory()
    submit_application(candidate=candidate, job=job, resume=resume_upload())

    with pytest.raises(ApplicationError, match="already applied"):
        submit_application(candidate=candidate, job=job, resume=resume_upload())
    assert Application.objects.count() == 1


def test_cannot_apply_to_closed_job():
    job = JobFactory(status=Job.Status.CLOSED)

    with pytest.raises(ApplicationError, match="no longer accepting"):
        submit_application(candidate=CandidateFactory(), job=job, resume=resume_upload())


def test_employer_moves_application_through_pipeline():
    application = ApplicationFactory()
    employer = application.job.company.owner

    for status in [S.SCREENING, S.INTERVIEW, S.OFFER, S.HIRED]:
        change_status(application=application, actor=employer, to_status=status)

    application.refresh_from_db()
    assert application.status == S.HIRED
    assert application.events.count() == 4


@pytest.mark.parametrize(("start", "target"), [(S.APPLIED, S.HIRED), (S.REJECTED, S.SCREENING)])
def test_invalid_transitions_are_rejected(start, target):
    application = ApplicationFactory(status=start)

    with pytest.raises(ApplicationError, match="Cannot move"):
        change_status(
            application=application, actor=application.job.company.owner, to_status=target
        )


def test_candidate_can_only_withdraw():
    application = ApplicationFactory()

    with pytest.raises(ApplicationError):
        change_status(application=application, actor=application.candidate, to_status=S.HIRED)

    change_status(application=application, actor=application.candidate, to_status=S.WITHDRAWN)
    application.refresh_from_db()
    assert application.status == S.WITHDRAWN


def test_strangers_cannot_change_status():
    application = ApplicationFactory()

    with pytest.raises(ApplicationError, match="cannot change"):
        change_status(application=application, actor=EmployerFactory(), to_status=S.SCREENING)


def test_only_employer_adds_internal_notes():
    application = ApplicationFactory()

    note = add_note(application=application, actor=application.job.company.owner, note="Strong")
    assert note.is_internal

    with pytest.raises(ApplicationError):
        add_note(application=application, actor=application.candidate, note="Hi")


def test_signals_fire_after_commit(django_capture_on_commit_callbacks):
    received = []

    def on_submitted(**kwargs):
        received.append("submitted")

    def on_changed(**kwargs):
        received.append(kwargs["to_status"])

    application_submitted.connect(on_submitted)
    application_status_changed.connect(on_changed)
    try:
        with django_capture_on_commit_callbacks(execute=True):
            application = submit_application(
                candidate=CandidateFactory(), job=JobFactory(), resume=resume_upload()
            )
        with django_capture_on_commit_callbacks(execute=True):
            change_status(
                application=application,
                actor=application.job.company.owner,
                to_status=S.SCREENING,
            )
    finally:
        application_submitted.disconnect(on_submitted)
        application_status_changed.disconnect(on_changed)

    assert received == ["submitted", "screening"]
