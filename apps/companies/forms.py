from django import forms

from .models import Company

MAX_LOGO_BYTES = 2 * 1024 * 1024


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ["name", "tagline", "about", "website", "headquarters", "size", "logo"]
        widgets = {"about": forms.Textarea(attrs={"rows": 6})}

    def clean_logo(self):
        logo = self.cleaned_data.get("logo")
        if logo and getattr(logo, "size", 0) > MAX_LOGO_BYTES:
            raise forms.ValidationError("Logos must be 2 MB or smaller.")
        return logo
