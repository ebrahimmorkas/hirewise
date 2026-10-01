from django.contrib import admin

from .models import Application, ApplicationEvent


class ApplicationEventInline(admin.TabularInline):
    model = ApplicationEvent
    extra = 0
    readonly_fields = ["actor", "from_status", "to_status", "note", "is_internal", "created_at"]


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ["candidate", "job", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["candidate__email", "job__title", "job__company__name"]
    list_select_related = ["candidate", "job"]
    inlines = [ApplicationEventInline]
