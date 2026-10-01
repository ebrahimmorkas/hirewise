from django import forms

from apps.jobs.models import Skill

from .models import CandidateProfile


class CandidateProfileForm(forms.ModelForm):
    skills_text = forms.CharField(
        label="Skills",
        required=False,
        help_text="Comma separated. Used to recommend matching jobs.",
    )

    class Meta:
        model = CandidateProfile
        fields = [
            "headline",
            "summary",
            "location",
            "years_experience",
            "resume",
            "linkedin_url",
            "github_url",
            "portfolio_url",
            "open_to_work",
        ]
        widgets = {"summary": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["resume"].widget.attrs["accept"] = "application/pdf"
        if self.instance.pk:
            self.fields["skills_text"].initial = ", ".join(
                self.instance.skills.values_list("name", flat=True)
            )

    def clean_skills_text(self):
        names = [n for n in self.cleaned_data.get("skills_text", "").split(",") if n.strip()]
        if len(names) > 30:
            raise forms.ValidationError("Add at most 30 skills.")
        return names

    def save(self, commit=True):
        profile = super().save(commit=commit)
        if commit:
            profile.skills.set(Skill.from_names(self.cleaned_data["skills_text"]))
        return profile
