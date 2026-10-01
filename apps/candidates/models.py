import uuid

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel
from apps.jobs.models import Skill

from .validators import validate_resume


def resume_upload_path(instance, filename: str) -> str:
    # Random names: resumes must not be discoverable by guessing URLs.
    return f"resumes/{uuid.uuid4().hex}.pdf"


class CandidateProfile(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    headline = models.CharField(max_length=120, blank=True, help_text="e.g. Backend Engineer")
    summary = models.TextField(blank=True)
    location = models.CharField(max_length=120, blank=True)
    years_experience = models.PositiveSmallIntegerField(null=True, blank=True)
    skills = models.ManyToManyField(Skill, related_name="candidates", blank=True)
    resume = models.FileField(
        upload_to=resume_upload_path, blank=True, validators=[validate_resume]
    )
    linkedin_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)
    portfolio_url = models.URLField(blank=True)
    open_to_work = models.BooleanField(default=True)

    COMPLETENESS_FIELDS = ("headline", "summary", "location", "years_experience", "resume")

    def __str__(self) -> str:
        return f"Profile of {self.user}"

    @property
    def completeness(self) -> int:
        """Percentage of key profile fields filled in (skills count as one field)."""
        filled = sum(
            1 for name in self.COMPLETENESS_FIELDS if getattr(self, name) not in ("", None)
        )
        has_skills = self.pk is not None and self.skills.exists()
        total = len(self.COMPLETENESS_FIELDS) + 1
        return round(100 * (filled + has_skills) / total)

    @classmethod
    def for_user(cls, user) -> "CandidateProfile":
        profile, _ = cls.objects.get_or_create(user=user)
        return profile
