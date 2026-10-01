from django.contrib import admin

from .models import JobAlert


@admin.register(JobAlert)
class JobAlertAdmin(admin.ModelAdmin):
    list_display = ["name", "candidate", "frequency", "is_active", "last_sent_at"]
    list_filter = ["frequency", "is_active"]
    search_fields = ["name", "candidate__email"]
