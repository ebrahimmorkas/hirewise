from datetime import timedelta

import django_filters
from django import forms
from django.db.models import Q
from django.utils import timezone

from .models import Job, Skill
from .search import search_jobs, uses_full_text_search


class JobFilter(django_filters.FilterSet):
    SORTS = [("relevance", "Most relevant"), ("newest", "Newest"), ("salary", "Highest salary")]
    POSTED = [("1", "Past 24 hours"), ("7", "Past week"), ("30", "Past month")]

    q = django_filters.CharFilter(
        method="filter_query",
        label="Keywords",
        widget=forms.TextInput(attrs={"placeholder": "Title, skill or company"}),
    )
    location = django_filters.CharFilter(field_name="location", lookup_expr="icontains")
    workplace = django_filters.MultipleChoiceFilter(
        choices=Job.Workplace.choices, widget=forms.CheckboxSelectMultiple
    )
    employment_type = django_filters.MultipleChoiceFilter(
        choices=Job.EmploymentType.choices, widget=forms.CheckboxSelectMultiple, label="Type"
    )
    level = django_filters.MultipleChoiceFilter(
        choices=Job.Level.choices, widget=forms.CheckboxSelectMultiple
    )
    min_salary = django_filters.NumberFilter(method="filter_min_salary", label="Minimum salary")
    skills = django_filters.ModelMultipleChoiceFilter(
        queryset=Skill.objects.all(), field_name="skills__slug", to_field_name="slug"
    )
    posted = django_filters.ChoiceFilter(
        choices=POSTED, method="filter_posted", label="Date posted", empty_label="Any time"
    )
    sort = django_filters.ChoiceFilter(
        choices=SORTS, method="filter_noop", label="Sort by", empty_label=None
    )

    class Meta:
        model = Job
        fields = []

    def filter_query(self, queryset, name, value):
        return search_jobs(queryset, value)

    def filter_min_salary(self, queryset, name, value):
        # A job qualifies if any part of its advertised range reaches the minimum.
        return queryset.filter(Q(salary_max__gte=value) | Q(salary_min__gte=value))

    def filter_posted(self, queryset, name, value):
        return queryset.filter(published_at__gte=timezone.now() - timedelta(days=int(value)))

    def filter_noop(self, queryset, name, value):
        return queryset  # ordering is applied in ``qs`` once all filters ran

    @property
    def qs(self):
        queryset = super().qs.distinct()
        data = self.form.cleaned_data if self.form.is_valid() else {}
        sort = data.get("sort") or "relevance"
        if sort == "salary":
            return queryset.order_by("-salary_max", "-salary_min", "-published_at")
        if sort == "relevance" and data.get("q") and uses_full_text_search():
            return queryset.order_by("-rank", "-published_at")
        return queryset.order_by("-published_at")
