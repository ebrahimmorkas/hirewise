"""Skill-based job recommendations.

Score = number of the candidate's skills the job asks for, computed in a single
query with a filtered ``Count``. Jobs the candidate already applied to are
excluded. ``match_percent`` tells the candidate how much of the job's skill list
they cover.
"""

from django.db.models import Count, F, FloatField, Q, QuerySet
from django.db.models.functions import Cast, Greatest

from .models import Job


def recommended_jobs(user, limit: int = 10) -> QuerySet[Job]:
    profile = getattr(user, "profile", None)
    if profile is None:
        return Job.objects.none()
    skill_ids = list(profile.skills.values_list("pk", flat=True))
    if not skill_ids:
        return Job.objects.none()

    return (
        Job.objects.published()
        .exclude(applications__candidate=user)
        .annotate(
            match_count=Count("skills", filter=Q(skills__in=skill_ids), distinct=True),
            skill_total=Count("skills", distinct=True),
        )
        .filter(match_count__gt=0)
        .annotate(
            match_percent=Cast(F("match_count") * 100, FloatField())
            / Cast(Greatest(F("skill_total"), 1), FloatField())
        )
        .select_related("company")
        .prefetch_related("skills")
        .order_by("-match_count", "-match_percent", "-published_at")[:limit]
    )


def candidate_skill_ids(user) -> set[int]:
    if not (user.is_authenticated and user.is_candidate):
        return set()
    profile = getattr(user, "profile", None)
    return set(profile.skills.values_list("pk", flat=True)) if profile else set()
