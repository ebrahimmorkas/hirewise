import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.accounts.tests.factories import CandidateFactory, EmployerFactory
from apps.applications.models import Application
from apps.applications.tests.factories import PDF_BYTES, ApplicationFactory
from apps.jobs.tests.factories import JobFactory

pytestmark = pytest.mark.django_db


def login(client, user):
    client.force_login(user)
    return client


def test_apply_flow(client):
    candidate, job = CandidateFactory(), JobFactory()
    login(client, candidate)

    response = client.post(
        reverse("applications:apply", args=[job.slug]),
        {
            "cover_letter": "Hire me",
            "resume": SimpleUploadedFile("cv.pdf", PDF_BYTES, content_type="application/pdf"),
        },
    )

    application = Application.objects.get()
    assert response.url == application.get_absolute_url()
    assert application.cover_letter == "Hire me"


def test_apply_requires_resume_when_profile_has_none(client):
    login(client, CandidateFactory())

    response = client.post(reverse("applications:apply", args=[JobFactory().slug]), {})

    assert "resume" in response.context["form"].errors


def test_second_visit_to_apply_redirects_to_existing_application(client):
    application = ApplicationFactory()
    login(client, application.candidate)

    response = client.get(reverse("applications:apply", args=[application.job.slug]))

    assert response.url == application.get_absolute_url()


def test_job_page_shows_applied_state(client):
    application = ApplicationFactory()
    login(client, application.candidate)

    assert b"Applied" in client.get(application.job.get_absolute_url()).content


def test_application_visible_to_candidate_and_employer_only(client):
    application = ApplicationFactory()
    url = application.get_absolute_url()

    assert login(client, application.candidate).get(url).status_code == 200
    assert login(client, application.job.company.owner).get(url).status_code == 200
    assert login(client, CandidateFactory()).get(url).status_code == 404
    assert login(client, EmployerFactory()).get(url).status_code == 404


def test_internal_notes_hidden_from_candidate(client):
    application = ApplicationFactory()
    employer = application.job.company.owner
    login(client, employer).post(
        reverse("applications:note", args=[application.pk]), {"note": "Salary expectations high"}
    )

    candidate_view = login(client, application.candidate).get(application.get_absolute_url())
    employer_view = login(client, employer).get(application.get_absolute_url())

    assert b"Salary expectations high" not in candidate_view.content
    assert b"Salary expectations high" in employer_view.content


def test_resume_download_is_access_controlled(client):
    application = ApplicationFactory()
    url = reverse("applications:resume", args=[application.pk])

    response = login(client, application.job.company.owner).get(url)
    assert response.status_code == 200
    assert b"".join(response.streaming_content) == PDF_BYTES
    assert "attachment" in response["Content-Disposition"]

    assert login(client, CandidateFactory()).get(url).status_code == 404


def test_pipeline_board_htmx_move(client):
    application = ApplicationFactory()
    employer = application.job.company.owner
    login(client, employer)

    response = client.post(
        reverse("applications:status", args=[application.pk]),
        {"status": "screening", "from": "board"},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert b'id="board"' in response.content
    application.refresh_from_db()
    assert application.status == "screening"


def test_pipeline_only_for_owning_employer(client):
    job = JobFactory()

    assert (
        login(client, EmployerFactory())
        .get(reverse("applications:pipeline", args=[job.slug]))
        .status_code
        == 404
    )
    assert (
        login(client, job.company.owner)
        .get(reverse("applications:pipeline", args=[job.slug]))
        .status_code
        == 200
    )


def test_candidate_withdraws(client):
    application = ApplicationFactory()
    login(client, application.candidate)

    response = client.post(
        reverse("applications:status", args=[application.pk]), {"status": "withdrawn"}
    )

    assert response.url == reverse("applications:mine")
    application.refresh_from_db()
    assert application.status == "withdrawn"


def test_dashboard_shows_applicant_counts(client):
    application = ApplicationFactory()
    ApplicationFactory(job=application.job, status="screening")
    login(client, application.job.company.owner)

    content = client.get(reverse("jobs:dashboard")).content.decode()

    assert ">2</a>" in content
    assert "1 new" in content
