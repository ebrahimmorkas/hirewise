import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.accounts.tests.factories import CandidateFactory, EmployerFactory
from apps.candidates.models import CandidateProfile
from apps.candidates.validators import MAX_RESUME_BYTES, validate_resume

pytestmark = pytest.mark.django_db

PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"


def pdf(name="cv.pdf", content=PDF_BYTES):
    return SimpleUploadedFile(name, content, content_type="application/pdf")


@pytest.fixture
def candidate_client(client):
    user = CandidateFactory()
    client.force_login(user)
    client.user = user
    return client


def test_profile_is_created_on_first_visit(candidate_client):
    response = candidate_client.get(reverse("candidates:profile"))

    assert response.status_code == 200
    assert CandidateProfile.objects.filter(user=candidate_client.user).exists()


def test_save_profile_with_resume_and_skills(candidate_client):
    response = candidate_client.post(
        reverse("candidates:profile"),
        {
            "headline": "Backend Engineer",
            "summary": "I build APIs.",
            "location": "Lisbon",
            "years_experience": 4,
            "skills_text": "Python, Django, Redis",
            "open_to_work": "on",
            "resume": pdf(),
        },
    )

    assert response.status_code == 302
    profile = candidate_client.user.profile
    assert profile.resume.name.startswith("resumes/") and profile.resume.name.endswith(".pdf")
    assert "cv" not in profile.resume.name  # original filename is not leaked
    assert profile.skills.count() == 3
    assert profile.completeness == 100


def test_completeness_counts_filled_fields():
    profile = CandidateProfile.for_user(CandidateFactory())
    assert profile.completeness == 0

    profile.headline = "Engineer"
    profile.location = "Remote"
    profile.save()
    assert profile.completeness == 33


@pytest.mark.parametrize(
    ("upload", "message"),
    [
        (pdf(name="cv.docx"), "as a PDF"),
        (pdf(content=b"MZ\x90\x00 not a pdf"), "valid PDF"),
        (pdf(content=b"%PDF-" + b"0" * MAX_RESUME_BYTES), "5 MB"),
    ],
)
def test_resume_validation(upload, message):
    with pytest.raises(ValidationError, match=message):
        validate_resume(upload)


def test_invalid_resume_is_rejected_by_form(candidate_client):
    response = candidate_client.post(
        reverse("candidates:profile"), {"resume": pdf(content=b"<html>evil</html>")}
    )

    assert "resume" in response.context["form"].errors


def test_employers_have_no_candidate_profile_page(client):
    client.force_login(EmployerFactory())

    assert client.get(reverse("candidates:profile")).status_code == 403
