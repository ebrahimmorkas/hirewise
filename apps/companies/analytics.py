"""Hiring analytics for an employer's company.

Every number is computed with aggregate queries (no per-row Python loops over
the database) and the result is cached briefly, which keeps the page fast even
for companies with many applications. Uses Redis when configured, otherwise the
local-memory cache.
"""

from datetime import timedelta

from django.core.cache import cache
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.applications.models import Application, ApplicationEvent
from apps.jobs.models import Job

CACHE_SECONDS = 300
TREND_DAYS = 30


def cache_key(company_id: int) -> str:
    return f"analytics:company:{company_id}"


def company_analytics(company) -> dict:
    return cache.get_or_set(cache_key(company.pk), lambda: _compute(company), CACHE_SECONDS)


def _compute(company) -> dict:
    jobs = Job.objects.filter(company=company)
    applications = Application.objects.filter(job__company=company)

    totals = jobs.aggregate(views=Sum("view_count"), jobs=Count("id"))
    total_views = totals["views"] or 0
    total_applications = applications.count()

    by_status = dict(applications.values_list("status").annotate(n=Count("id")))
    # An application "reached" a stage if its history ever entered that stage or a
    # later one, so candidates rejected after an interview still count as interviewed.
    events = ApplicationEvent.objects.filter(application__job__company=company)
    reached = {
        stage: events.filter(to_status__in=Application.PIPELINE[index:])
        .values("application")
        .distinct()
        .count()
        for index, stage in enumerate(Application.PIPELINE)
    }
    reached[Application.Status.APPLIED] = total_applications  # every application starts here
    funnel = [
        {
            "stage": Application.Status(stage).label,
            "count": count,
            "percent": round(100 * count / total_applications) if total_applications else 0,
        }
        for stage, count in reached.items()
    ]

    since = timezone.now() - timedelta(days=TREND_DAYS - 1)
    per_day = dict(
        applications.filter(created_at__gte=since)
        .annotate(day=TruncDate("created_at"))
        .values_list("day")
        .annotate(n=Count("id"))
    )
    today = timezone.now().date()
    trend = [
        {"day": day, "count": per_day.get(day, 0)}
        for day in (today - timedelta(days=offset) for offset in range(TREND_DAYS - 1, -1, -1))
    ]
    peak = max((point["count"] for point in trend), default=0) or 1
    for point in trend:
        point["height"] = round(100 * point["count"] / peak)

    top_jobs = (
        jobs.annotate(applicant_count=Count("applications"))
        .order_by("-applicant_count", "-view_count")
        .values("title", "slug", "view_count", "applicant_count")[:5]
    )

    return {
        "open_jobs": jobs.published().count(),
        "total_jobs": totals["jobs"],
        "total_views": total_views,
        "total_applications": total_applications,
        "conversion_rate": round(100 * total_applications / total_views, 1) if total_views else 0,
        "hired": by_status.get(Application.Status.HIRED, 0),
        "funnel": funnel,
        "trend": trend,
        "top_jobs": list(top_jobs),
        "generated_at": timezone.now(),
    }
