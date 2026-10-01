from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.core.models import TimeStampedModel
from apps.core.text import unique_slug


class Company(TimeStampedModel):
    class Size(models.TextChoices):
        STARTUP = "1-10", "1-10 employees"
        SMALL = "11-50", "11-50 employees"
        MEDIUM = "51-200", "51-200 employees"
        LARGE = "201-1000", "201-1000 employees"
        ENTERPRISE = "1000+", "1000+ employees"

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="company"
    )
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    tagline = models.CharField(max_length=160, blank=True)
    about = models.TextField(blank=True)
    website = models.URLField(blank=True)
    headquarters = models.CharField(max_length=120, blank=True)
    size = models.CharField(max_length=10, choices=Size.choices, blank=True)
    logo = models.ImageField(upload_to="logos/", blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "companies"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("companies:detail", args=[self.slug])

    @property
    def initials(self) -> str:
        return "".join(word[0] for word in self.name.split()[:2]).upper()
