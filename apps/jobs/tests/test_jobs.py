from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.tests.factories import CandidateFactory, EmployerFactory
from apps.jobs.models import Job, Skill
from apps.jobs.tests.factories import CompanyFactory, JobFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def company():
    return CompanyFactory(name="Globex")


@pytest.fixture
def employer_client(client, company):
    client.force_login(company.owner)
    return client


def job_payload(**overrides):
    data = {
        "title": "Senior Django Developer",
        "description": "Own our core platform.",
        "location": "Remote - EU",
        "workplace": "remote",
        "employment_type": "full_time",
        "level": "senior",
        "salary_min": "90000",
        "salary_max": "120000",
        "salary_currency": "EUR",
        "skills_text": "Python, Django, python , PostgreSQL",
    }
    data.update(overrides)
    return data


# --- model ---------------------------------------------------------------------


def test_published_queryset_excludes_drafts_closed_and_expired():
    live = JobFactory()
    JobFactory(draft=True)
    JobFactory(status=Job.Status.CLOSED)
    JobFactory(expires_at=timezone.now() - timedelta(minutes=1))

    assert list(Job.objects.published()) == [live]


def test_publish_sets_dates(settings):
    settings.HIREWISE_JOB_LIFETIME_DAYS = 14
    job = JobFactory(draft=True)

    job.publish()

    assert job.is_open
    assert (job.expires_at - job.published_at).days == 14


def test_skills_are_deduplicated_by_slug():
    skills = Skill.from_names(["Python", "python ", " PYTHON", "Go"])

    assert [s.name for s in skills] == ["Python", "Go"]
    assert Skill.objects.count() == 2


@pytest.mark.parametrize(
    ("low", "high", "expected"),
    [(60000, 80000, "USD 60k–80k"), (60000, None, "USD 60k+"), (None, 75000, "up to USD 75k")],
)
def test_salary_display(low, high, expected):
    assert Job(salary_min=low, salary_max=high).salary_display == expected


def test_slug_includes_company_and_is_unique(company):
    first = JobFactory(company=company, title="Data Engineer")
    second = JobFactory(company=company, title="Data Engineer")

    assert first.slug == "data-engineer-globex"
    assert second.slug == "data-engineer-globex-2"


# --- employer flows --------------------------------------------------------------


def test_employer_without_company_is_sent_to_company_setup(client):
    client.force_login(EmployerFactory())

    response = client.get(reverse("jobs:create"))

    assert response.status_code == 302
    assert response.url == reverse("companies:create")


def test_create_company_profile(client):
    employer = EmployerFactory()
    client.force_login(employer)

    response = client.post(reverse("companies:create"), {"name": "Initech", "size": "11-50"})

    assert response.status_code == 302
    assert employer.company.slug == "initech"


def test_candidates_cannot_post_jobs(client):
    client.force_login(CandidateFactory())

    assert client.get(reverse("jobs:create")).status_code == 403


def test_post_and_publish_job(employer_client, company):
    response = employer_client.post(reverse("jobs:create"), {**job_payload(), "publish": "1"})

    job = Job.objects.get()
    assert response.status_code == 302
    assert job.company == company
    assert job.is_open
    assert sorted(job.skills.values_list("name", flat=True)) == ["Django", "PostgreSQL", "Python"]


def test_save_as_draft(employer_client):
    employer_client.post(reverse("jobs:create"), job_payload())

    assert Job.objects.get().status == Job.Status.DRAFT


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"salary_min": "100000", "salary_max": "50000"}, "salary_max"),
        ({"workplace": "onsite", "location": ""}, "location"),
        ({"skills_text": ",".join(f"s{i}" for i in range(16))}, "skills_text"),
    ],
)
def test_job_form_validation(employer_client, overrides, field):
    response = employer_client.post(reverse("jobs:create"), job_payload(**overrides))

    assert field in response.context["form"].errors


def test_close_and_republish(employer_client, company):
    job = JobFactory(company=company)

    employer_client.post(reverse("jobs:status", args=[job.slug, "close"]))
    job.refresh_from_db()
    assert job.status == Job.Status.CLOSED

    employer_client.post(reverse("jobs:status", args=[job.slug, "publish"]))
    job.refresh_from_db()
    assert job.is_open


def test_employer_cannot_edit_other_companies_jobs(employer_client):
    other = JobFactory()

    assert employer_client.get(reverse("jobs:edit", args=[other.slug])).status_code == 404


def test_dashboard_lists_own_jobs(employer_client, company):
    JobFactory(company=company, title="Mine")
    JobFactory(title="Theirs")

    content = employer_client.get(reverse("jobs:dashboard")).content.decode()

    assert "Mine" in content and "Theirs" not in content


# --- public pages ------------------------------------------------------------------


def test_job_detail_counts_views_for_visitors_only(client, company):
    job = JobFactory(company=company)

    client.get(job.get_absolute_url())
    client.get(job.get_absolute_url())
    client.force_login(company.owner)
    client.get(job.get_absolute_url())

    job.refresh_from_db()
    assert job.view_count == 2


def test_drafts_are_hidden_from_public_but_visible_to_owner(client, company):
    job = JobFactory(company=company, draft=True)

    assert client.get(job.get_absolute_url()).status_code == 404
    client.force_login(company.owner)
    assert client.get(job.get_absolute_url()).status_code == 200


def test_company_page_lists_open_jobs(client, company):
    JobFactory(company=company, title="Open role")
    JobFactory(company=company, title="Secret draft", draft=True)

    content = client.get(company.get_absolute_url()).content.decode()

    assert "Open role" in content and "Secret draft" not in content


def test_home_shows_latest_jobs(client):
    JobFactory(title="Platform Engineer")

    assert b"Platform Engineer" in client.get(reverse("home")).content
