from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from apps.companies.models import Company
from apps.core.models import TimeStampedModel
from apps.core.text import unique_slug


class Skill(models.Model):
    name = models.CharField(max_length=60)
    slug = models.SlugField(max_length=70, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @classmethod
    def from_names(cls, names) -> list["Skill"]:
        """Get or create skills from free-text names, de-duplicated by slug."""
        skills = {}
        for raw in names:
            name = raw.strip()
            slug = slugify(name)
            if slug and slug not in skills:
                skills[slug], _ = cls.objects.get_or_create(slug=slug, defaults={"name": name})
        return list(skills.values())


class JobQuerySet(models.QuerySet):
    def published(self):
        now = timezone.now()
        return self.filter(status=Job.Status.PUBLISHED, published_at__lte=now).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=now)
        )


class Job(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        CLOSED = "closed", "Closed"

    class Workplace(models.TextChoices):
        ONSITE = "onsite", "On-site"
        HYBRID = "hybrid", "Hybrid"
        REMOTE = "remote", "Remote"

    class EmploymentType(models.TextChoices):
        FULL_TIME = "full_time", "Full-time"
        PART_TIME = "part_time", "Part-time"
        CONTRACT = "contract", "Contract"
        INTERNSHIP = "internship", "Internship"

    class Level(models.TextChoices):
        ENTRY = "entry", "Entry level"
        MID = "mid", "Mid level"
        SENIOR = "senior", "Senior"
        LEAD = "lead", "Lead / Principal"

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="jobs")
    title = models.CharField(max_length=140)
    slug = models.SlugField(max_length=160, unique=True)
    description = models.TextField()
    location = models.CharField(max_length=120, blank=True)
    workplace = models.CharField(max_length=10, choices=Workplace.choices)
    employment_type = models.CharField(max_length=12, choices=EmploymentType.choices)
    level = models.CharField(max_length=10, choices=Level.choices)
    salary_min = models.PositiveIntegerField(null=True, blank=True)
    salary_max = models.PositiveIntegerField(null=True, blank=True)
    salary_currency = models.CharField(max_length=3, default="USD")
    skills = models.ManyToManyField(Skill, related_name="jobs", blank=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    view_count = models.PositiveIntegerField(default=0, editable=False)

    objects = JobQuerySet.as_manager()

    class Meta:
        ordering = ["-published_at", "-created_at"]
        indexes = [models.Index(fields=["status", "-published_at"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(salary_max__isnull=True)
                | Q(salary_min__isnull=True)
                | Q(salary_max__gte=F("salary_min")),
                name="job_salary_range_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.title} at {self.company}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, f"{self.title} {self.company.name}")
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("jobs:detail", args=[self.slug])

    def publish(self) -> None:
        now = timezone.now()
        self.status = self.Status.PUBLISHED
        self.published_at = now
        self.expires_at = now + timedelta(days=settings.HIREWISE_JOB_LIFETIME_DAYS)
        self.save(update_fields=["status", "published_at", "expires_at", "updated_at"])

    def close(self) -> None:
        self.status = self.Status.CLOSED
        self.save(update_fields=["status", "updated_at"])

    @property
    def is_open(self) -> bool:
        return (
            self.status == self.Status.PUBLISHED
            and self.published_at is not None
            and (self.expires_at is None or self.expires_at > timezone.now())
        )

    @property
    def salary_display(self) -> str:
        if not (self.salary_min or self.salary_max):
            return ""
        fmt = lambda value: f"{value / 1000:g}k"  # noqa: E731
        if self.salary_min and self.salary_max:
            return f"{self.salary_currency} {fmt(self.salary_min)}–{fmt(self.salary_max)}"
        if self.salary_min:
            return f"{self.salary_currency} {fmt(self.salary_min)}+"
        return f"up to {self.salary_currency} {fmt(self.salary_max)}"
