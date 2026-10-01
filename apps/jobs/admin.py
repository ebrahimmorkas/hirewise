from django.contrib import admin

from .models import Job, SavedJob, Skill


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "company",
        "status",
        "workplace",
        "level",
        "published_at",
        "view_count",
    ]
    list_filter = ["status", "workplace", "employment_type", "level"]
    search_fields = ["title", "company__name"]
    autocomplete_fields = ["skills"]
    list_select_related = ["company"]
    date_hierarchy = "published_at"


@admin.register(SavedJob)
class SavedJobAdmin(admin.ModelAdmin):
    list_display = ["candidate", "job", "created_at"]
    list_select_related = ["candidate", "job"]
