from django.contrib import admin

from .models import CandidateProfile


@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "headline", "location", "years_experience", "open_to_work"]
    list_filter = ["open_to_work"]
    search_fields = ["user__email", "user__full_name", "headline"]
    autocomplete_fields = ["skills"]
