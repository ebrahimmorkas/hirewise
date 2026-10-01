import pytest
from django.urls import reverse

from apps.accounts.tests.factories import CandidateFactory
from apps.applications.tests.factories import ApplicationFactory
from apps.candidates.models import CandidateProfile
from apps.jobs.models import Skill
from apps.jobs.recommendations import recommended_jobs
from apps.jobs.tests.factories import JobFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def candidate():
    user = CandidateFactory()
    profile = CandidateProfile.for_user(user)
    profile.skills.set(Skill.from_names(["Python", "Django", "PostgreSQL"]))
    return user


def test_jobs_ranked_by_number_of_matching_skills(candidate):
    JobFactory(title="One match", skills=["Python", "Java"])
    JobFactory(title="Three matches", skills=["Python", "Django", "PostgreSQL", "AWS"])
    JobFactory(title="No match", skills=["Swift"])

    jobs = list(recommended_jobs(candidate))

    assert [j.title for j in jobs] == ["Three matches", "One match"]
    assert jobs[0].match_count == 3
    assert jobs[0].match_percent == 75.0


def test_applied_and_unpublished_jobs_are_excluded(candidate):
    applied = JobFactory(title="Applied", skills=["Python"])
    ApplicationFactory(job=applied, candidate=candidate)
    JobFactory(title="Draft", skills=["Python"], draft=True)

    assert list(recommended_jobs(candidate)) == []


def test_no_skills_means_no_recommendations():
    user = CandidateFactory()
    CandidateProfile.for_user(user)
    JobFactory(skills=["Python"])

    assert list(recommended_jobs(user)) == []


def test_recommended_page_highlights_matching_skills(client, candidate):
    JobFactory(title="Django role", skills=["Django", "Rust"])
    client.force_login(candidate)

    content = client.get(reverse("jobs:recommended")).content.decode()

    assert "Django role" in content
    assert 'tag tag--match">Django<' in content
    assert 'class="tag">Rust<' in content


def test_home_shows_recommendations_for_candidates(client, candidate):
    JobFactory(title="Perfect fit", skills=["Python", "Django"])
    client.force_login(candidate)

    assert b"Recommended for you" in client.get(reverse("home")).content
