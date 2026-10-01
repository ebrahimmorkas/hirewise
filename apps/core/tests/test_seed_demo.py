import pytest
from django.core.management import call_command

from apps.applications.models import Application
from apps.jobs.models import Job


@pytest.mark.django_db
def test_seed_demo_is_idempotent():
    call_command("seed_demo")
    call_command("seed_demo")

    assert Job.objects.published().count() == 7
    assert Application.objects.count() == 6
    assert Application.objects.filter(status="interview").count() == 1
