from django import forms

from apps.candidates.validators import validate_resume


class ApplyForm(forms.Form):
    cover_letter = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 8}),
        required=False,
        max_length=5000,
        help_text="Optional, but a short note on why you're a fit goes a long way.",
    )
    resume = forms.FileField(
        required=False,
        validators=[validate_resume],
        help_text="PDF, max 5 MB. Leave empty to use the resume from your profile.",
        widget=forms.ClearableFileInput(attrs={"accept": "application/pdf"}),
    )

    def __init__(self, *args, has_profile_resume: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.has_profile_resume = has_profile_resume
        if not has_profile_resume:
            self.fields["resume"].help_text = "PDF, max 5 MB."

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("resume") and not self.has_profile_resume:
            self.add_error("resume", "Please attach your resume.")
        return cleaned


class NoteForm(forms.Form):
    note = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), max_length=2000)
