from django.core.management.base import BaseCommand

from apps.notifications.tasks import send_job_alerts


class Command(BaseCommand):
    help = "Send job-alert digests that are due (cron alternative to Celery beat)."

    def handle(self, *args, **options):
        count = send_job_alerts()
        self.stdout.write(self.style.SUCCESS(f"Sent {count} job alert digest(s)."))
