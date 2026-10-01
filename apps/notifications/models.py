from django.conf import settings
from django.core import signing
from django.db import models
from django.urls import reverse

from apps.core.models import TimeStampedModel

UNSUBSCRIBE_SALT = "hirewise.job-alert.unsubscribe"


class JobAlert(TimeStampedModel):
    """A saved search. Matching new jobs are emailed as a periodic digest.

    ``params`` holds the job-search query parameters exactly as submitted, so
    alerts are matched with the very same ``JobFilter`` used by the search page.
    """

    class Frequency(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"

    candidate = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="job_alerts"
    )
    name = models.CharField(max_length=120)
    params = models.JSONField(default=dict)
    frequency = models.CharField(max_length=8, choices=Frequency.choices, default=Frequency.DAILY)
    is_active = models.BooleanField(default=True)
    last_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.candidate})"

    def unsubscribe_token(self) -> str:
        return signing.dumps(self.pk, salt=UNSUBSCRIBE_SALT)

    def unsubscribe_url(self) -> str:
        path = reverse("notifications:unsubscribe", args=[self.unsubscribe_token()])
        return f"{settings.SITE_URL.rstrip('/')}{path}"

    @classmethod
    def from_token(cls, token: str) -> "JobAlert | None":
        try:
            pk = signing.loads(token, salt=UNSUBSCRIBE_SALT)
        except signing.BadSignature:
            return None
        return cls.objects.filter(pk=pk).first()
