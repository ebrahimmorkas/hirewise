from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.tests.factories import CandidateFactory, EmployerFactory
from apps.jobs.models import Job, SavedJob
from apps.jobs.search import uses_full_text_search
from apps.jobs.tests.factories import CompanyFactory, JobFactory

pytestmark = pytest.mark.django_db


def search(client, **params):
    response = client.get(reverse("jobs:list"), params)
    return [job.title for job in response.context["jobs"]]


def test_list_shows_only_published_jobs(client):
    JobFactory(title="Visible")
    JobFactory(title="Hidden draft", draft=True)

    assert search(client) == ["Visible"]


def test_keyword_matches_title_description_company_and_skill(client):
    JobFactory(title="Django Developer")
    JobFactory(title="Backend Engineer", description="We use Django heavily.")
    JobFactory(title="Platform Engineer", company=CompanyFactory(name="Djangonauts Inc"))
    JobFactory(title="SRE", skills=["Django"])
    JobFactory(title="iOS Developer", description="Swift only.")

    results = search(client, q="django")

    assert "iOS Developer" not in results
    assert {"Django Developer", "Backend Engineer", "SRE"} <= set(results)


def test_multiple_filters_combine(client):
    match = JobFactory(
        title="Match", workplace=Job.Workplace.REMOTE, level=Job.Level.SENIOR, location=""
    )
    JobFactory(title="Wrong level", workplace=Job.Workplace.REMOTE, level=Job.Level.ENTRY)
    JobFactory(title="Wrong workplace", workplace=Job.Workplace.ONSITE, level=Job.Level.SENIOR)

    assert search(client, workplace="remote", level="senior") == [match.title]


def test_multi_select_filter_is_or_within_field(client):
    JobFactory(title="Remote", workplace=Job.Workplace.REMOTE)
    JobFactory(title="Hybrid", workplace=Job.Workplace.HYBRID)
    JobFactory(title="Onsite", workplace=Job.Workplace.ONSITE)

    assert set(search(client, workplace=["remote", "hybrid"])) == {"Remote", "Hybrid"}


def test_min_salary_matches_upper_end_of_range(client):
    JobFactory(title="Reaches", salary_min=70000, salary_max=100000)
    JobFactory(title="Too low", salary_min=40000, salary_max=60000)

    assert search(client, min_salary=90000) == ["Reaches"]


def test_skill_filter(client):
    JobFactory(title="Go role", skills=["Go", "Kubernetes"])
    JobFactory(title="Python role", skills=["Python"])

    assert search(client, skills="kubernetes") == ["Go role"]


def test_posted_within_filter(client):
    JobFactory(title="Fresh", published_at=timezone.now() - timedelta(hours=2))
    JobFactory(title="Old", published_at=timezone.now() - timedelta(days=10))

    assert search(client, posted="7") == ["Fresh"]


def test_sort_by_salary(client):
    JobFactory(title="Mid", salary_min=50000, salary_max=70000)
    JobFactory(title="Top", salary_min=150000, salary_max=200000)

    assert search(client, sort="salary") == ["Top", "Mid"]


def test_htmx_returns_results_fragment(client):
    JobFactory()

    response = client.get(reverse("jobs:list"), headers={"HX-Request": "true"})

    assert response.templates[0].name == "jobs/_results.html"


@pytest.mark.skipif(not uses_full_text_search(), reason="PostgreSQL full-text search only")
def test_postgres_ranks_title_matches_above_description_matches(client):
    JobFactory(title="Office Manager", description="Help our Kubernetes team stay organised.")
    JobFactory(title="Kubernetes Engineer", description="Run clusters.")

    assert search(client, q="kubernetes")[0] == "Kubernetes Engineer"


@pytest.mark.skipif(not uses_full_text_search(), reason="PostgreSQL full-text search only")
def test_postgres_stemming_and_websearch_syntax(client):
    JobFactory(title="Engineering Manager")
    JobFactory(title="Data Analyst", description="Reporting for the engineering org.")

    assert "Engineering Manager" in search(client, q="engineers")
    assert search(client, q="engineering -analyst") == ["Engineering Manager"]


# --- saved jobs ----------------------------------------------------------------------


def test_candidate_saves_and_unsaves_job(client):
    candidate = CandidateFactory()
    client.force_login(candidate)
    job = JobFactory()
    url = reverse("jobs:save", args=[job.slug])

    response = client.post(url, headers={"HX-Request": "true"})
    assert b"Saved" in response.content
    assert SavedJob.objects.filter(candidate=candidate, job=job).exists()

    client.post(url, headers={"HX-Request": "true"})
    assert not SavedJob.objects.exists()


def test_saved_jobs_page(client):
    candidate = CandidateFactory()
    client.force_login(candidate)
    SavedJob.objects.create(candidate=candidate, job=JobFactory(title="Bookmarked"))

    assert b"Bookmarked" in client.get(reverse("jobs:saved")).content


def test_employers_cannot_save_jobs(client):
    client.force_login(EmployerFactory())

    assert client.post(reverse("jobs:save", args=[JobFactory().slug])).status_code == 403
