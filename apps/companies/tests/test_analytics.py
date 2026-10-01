import pytest
from django.core.cache import cache
from django.urls import reverse

from apps.accounts.tests.factories import CandidateFactory, EmployerFactory
from apps.applications.services import change_status
from apps.applications.tests.factories import ApplicationFactory
from apps.companies.analytics import cache_key, company_analytics
from apps.jobs.tests.factories import CompanyFactory, JobFactory

pytestmark = pytest.mark.django_db


def advance(application, *statuses):
    for status in statuses:
        change_status(
            application=application, actor=application.job.company.owner, to_status=status
        )


@pytest.fixture
def company():
    company = CompanyFactory()
    job = JobFactory(company=company, title="Backend")
    job.view_count = 200
    job.save()
    JobFactory(company=company, title="Frontend", draft=True)

    hired = ApplicationFactory(job=job)
    advance(hired, "screening", "interview", "offer", "hired")
    rejected_after_interview = ApplicationFactory(job=job)
    advance(rejected_after_interview, "interview", "rejected")
    ApplicationFactory(job=job)  # still "applied" (no events created by the factory)
    ApplicationFactory()  # another company
    return company


def test_totals_and_conversion(company):
    stats = company_analytics(company)

    assert stats["open_jobs"] == 1
    assert stats["total_jobs"] == 2
    assert stats["total_views"] == 200
    assert stats["total_applications"] == 3
    assert stats["conversion_rate"] == 1.5
    assert stats["hired"] == 1


def test_funnel_counts_stages_reached_from_history(company):
    funnel = {step["stage"]: step["count"] for step in company_analytics(company)["funnel"]}

    assert funnel["Applied"] == 3
    assert funnel["Screening"] == 2  # interview counts as having passed screening
    assert funnel["Interview"] == 2  # hired one + the one rejected after interview
    assert funnel["Offer"] == 1
    assert funnel["Hired"] == 1


def test_trend_covers_30_days(company):
    trend = company_analytics(company)["trend"]

    assert len(trend) == 30
    assert trend[-1]["count"] == 3
    assert trend[-1]["height"] == 100


def test_results_are_cached(company, django_assert_num_queries):
    company_analytics(company)
    assert cache.get(cache_key(company.pk)) is not None

    with django_assert_num_queries(0):
        company_analytics(company)


def test_company_edit_forbids_candidates(client):
    client.force_login(CandidateFactory())

    assert client.get(reverse("companies:edit")).status_code == 403


def test_analytics_page_access(client, company):
    client.force_login(company.owner)
    assert client.get(reverse("companies:analytics")).status_code == 200

    client.force_login(CandidateFactory())
    assert client.get(reverse("companies:analytics")).status_code == 403

    client.force_login(EmployerFactory())  # no company yet
    assert client.get(reverse("companies:analytics")).url == reverse("companies:create")
