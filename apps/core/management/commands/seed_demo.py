from datetime import timedelta

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.applications.models import Application
from apps.applications.services import change_status, submit_application
from apps.candidates.models import CandidateProfile
from apps.companies.models import Company
from apps.jobs.models import Job, Skill

DEMO_PASSWORD = "demo-pass-123"

# Smallest valid single-page PDF, used as a placeholder resume.
DEMO_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF\n"
)

COMPANIES = [
    ("Northwind Analytics", "Data products for logistics teams.", "Berlin", "51-200"),
    ("Brightpath Health", "Making healthcare scheduling painless.", "London", "201-1000"),
    ("Pixelforge Studios", "Indie studio building cosy games.", "Lisbon", "11-50"),
]

JOBS = [
    # company index, title, workplace, level, type, location, salary, skills, days ago
    (
        0,
        "Senior Django Engineer",
        "remote",
        "senior",
        "full_time",
        "",
        (95000, 125000),
        ["Python", "Django", "PostgreSQL", "Celery", "Redis"],
        1,
    ),
    (
        0,
        "Data Engineer",
        "hybrid",
        "mid",
        "full_time",
        "Berlin",
        (70000, 90000),
        ["Python", "SQL", "Airflow", "AWS"],
        3,
    ),
    (
        1,
        "Backend Developer (Python)",
        "onsite",
        "mid",
        "full_time",
        "London",
        (60000, 80000),
        ["Python", "FastAPI", "PostgreSQL", "Docker"],
        2,
    ),
    (
        1,
        "Junior QA Engineer",
        "hybrid",
        "entry",
        "full_time",
        "London",
        (35000, 42000),
        ["Testing", "Python", "Selenium"],
        6,
    ),
    (
        1,
        "Engineering Manager",
        "remote",
        "lead",
        "full_time",
        "",
        (130000, 160000),
        ["Leadership", "Python", "Kubernetes"],
        9,
    ),
    (2, "Gameplay Programmer", "onsite", "mid", "contract", "Lisbon", None, ["C#", "Unity"], 4),
    (
        2,
        "Backend Intern",
        "remote",
        "entry",
        "internship",
        "",
        (18000, 22000),
        ["Python", "Django"],
        0,
    ),
]


class Command(BaseCommand):
    help = "Create demo employers, companies, jobs, a candidate profile and applications."

    @transaction.atomic
    def handle(self, *args, **options):
        if Company.objects.filter(name=COMPANIES[0][0]).exists():
            self.stdout.write("Demo data already present.")
            return

        companies = []
        for index, (name, tagline, hq, size) in enumerate(COMPANIES):
            owner = self._user(f"employer{index + 1}@hirewise.dev", f"{name} Recruiter", "employer")
            companies.append(
                Company.objects.create(
                    owner=owner,
                    name=name,
                    tagline=tagline,
                    headquarters=hq,
                    size=size,
                    about=f"{name}. {tagline} We value craft, ownership and kindness.",
                )
            )

        now = timezone.now()
        jobs = []
        for company_idx, title, workplace, level, kind, location, salary, skills, age in JOBS:
            job = Job.objects.create(
                company=companies[company_idx],
                title=title,
                description=(
                    f"We're hiring a {title} to join {companies[company_idx].name}.\n\n"
                    "What you'll do:\n- Ship features end to end\n- Improve reliability\n"
                    "- Mentor teammates\n\nWhat we offer:\n- Flexible hours\n- Learning budget"
                ),
                workplace=workplace,
                level=level,
                employment_type=kind,
                location=location,
                salary_min=salary[0] if salary else None,
                salary_max=salary[1] if salary else None,
                salary_currency="EUR" if company_idx != 1 else "GBP",
                status=Job.Status.PUBLISHED,
                published_at=now - timedelta(days=age),
                expires_at=now + timedelta(days=30 - age),
                view_count=40 + 17 * len(skills),
            )
            job.skills.set(Skill.from_names(skills))
            jobs.append(job)

        candidate = self._user("candidate@hirewise.dev", "Sam Rivera", "candidate")
        profile = CandidateProfile.for_user(candidate)
        profile.headline = "Python Backend Engineer"
        profile.summary = "4 years building Django and FastAPI services. Loves clean APIs."
        profile.location = "Porto, Portugal"
        profile.years_experience = 4
        profile.github_url = "https://github.com/"
        profile.resume.save("resume.pdf", ContentFile(DEMO_PDF))
        profile.save()
        profile.skills.set(Skill.from_names(["Python", "Django", "PostgreSQL", "Docker", "Redis"]))

        submit_application(candidate=candidate, job=jobs[2], cover_letter="I'd love to help!")
        first = submit_application(candidate=candidate, job=jobs[1])
        change_status(application=first, actor=companies[0].owner, to_status="screening")
        change_status(
            application=first,
            actor=companies[0].owner,
            to_status="interview",
            note="Could you do a 45 minute call next Tuesday?",
        )

        for n in range(4):
            applicant = self._user(
                f"applicant{n + 1}@hirewise.dev", f"Applicant {n + 1}", "candidate"
            )
            submit_application(
                candidate=applicant, job=jobs[0], resume=ContentFile(DEMO_PDF, name="cv.pdf")
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {len(companies)} companies, {len(jobs)} jobs, "
                f"{Application.objects.count()} applications.\n"
                f"  employer:  employer1@hirewise.dev / {DEMO_PASSWORD}\n"
                f"  candidate: candidate@hirewise.dev / {DEMO_PASSWORD}"
            )
        )

    @staticmethod
    def _user(email: str, name: str, role: str) -> User:
        user = User.objects.create_user(email=email, password=DEMO_PASSWORD, full_name=name)
        user.role = role
        user.save(update_fields=["role"])
        return user
