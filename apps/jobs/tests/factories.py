from datetime import timedelta

import factory
from django.utils import timezone

from apps.accounts.tests.factories import EmployerFactory
from apps.companies.models import Company
from apps.jobs.models import Job, Skill


class CompanyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Company

    owner = factory.SubFactory(EmployerFactory)
    name = factory.Sequence(lambda n: f"Acme {n}")
    about = "We build things."


class SkillFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Skill
        django_get_or_create = ["slug"]

    name = factory.Sequence(lambda n: f"Skill {n}")
    slug = factory.LazyAttribute(lambda o: o.name.lower().replace(" ", "-"))


class JobFactory(factory.django.DjangoModelFactory):
    """A published, open job by default."""

    class Meta:
        model = Job
        skip_postgeneration_save = True

    company = factory.SubFactory(CompanyFactory)
    title = factory.Sequence(lambda n: f"Backend Engineer {n}")
    description = "Build and scale our Django services."
    location = "Berlin"
    workplace = Job.Workplace.HYBRID
    employment_type = Job.EmploymentType.FULL_TIME
    level = Job.Level.MID
    salary_min = 60000
    salary_max = 80000
    status = Job.Status.PUBLISHED
    published_at = factory.LazyFunction(lambda: timezone.now() - timedelta(days=1))
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(days=29))

    @factory.post_generation
    def skills(self, create, extracted, **kwargs):
        if create and extracted:
            self.skills.set(Skill.from_names(extracted))

    class Params:
        draft = factory.Trait(status=Job.Status.DRAFT, published_at=None, expires_at=None)
