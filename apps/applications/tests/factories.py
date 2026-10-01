import factory
from django.core.files.base import ContentFile

from apps.accounts.tests.factories import CandidateFactory
from apps.applications.models import Application
from apps.jobs.tests.factories import JobFactory

PDF_BYTES = b"%PDF-1.7\n%%EOF"


class ApplicationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Application

    job = factory.SubFactory(JobFactory)
    candidate = factory.SubFactory(CandidateFactory)
    cover_letter = "I'd love to join."
    resume = factory.LazyFunction(lambda: ContentFile(PDF_BYTES, name="resume.pdf"))
