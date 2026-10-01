from django import forms

from .models import Job, Skill


class JobForm(forms.ModelForm):
    skills_text = forms.CharField(
        label="Skills",
        required=False,
        help_text="Comma separated, e.g. Python, Django, PostgreSQL",
    )

    class Meta:
        model = Job
        fields = [
            "title",
            "description",
            "location",
            "workplace",
            "employment_type",
            "level",
            "salary_min",
            "salary_max",
            "salary_currency",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 10})}
        labels = {"salary_min": "Salary from (yearly)", "salary_max": "Salary to (yearly)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["skills_text"].initial = ", ".join(
                self.instance.skills.values_list("name", flat=True)
            )

    def clean(self):
        cleaned = super().clean()
        low, high = cleaned.get("salary_min"), cleaned.get("salary_max")
        if low and high and high < low:
            self.add_error("salary_max", "Must be greater than or equal to the minimum.")
        if cleaned.get("workplace") != Job.Workplace.REMOTE and not cleaned.get("location"):
            self.add_error("location", "Location is required for on-site and hybrid roles.")
        return cleaned

    def clean_skills_text(self):
        names = [n for n in self.cleaned_data.get("skills_text", "").split(",") if n.strip()]
        if len(names) > 15:
            raise forms.ValidationError("Add at most 15 skills.")
        return names

    def save(self, commit=True):
        job = super().save(commit=commit)
        if commit:
            job.skills.set(Skill.from_names(self.cleaned_data["skills_text"]))
        return job
