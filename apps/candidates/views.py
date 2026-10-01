from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import UpdateView

from apps.accounts.mixins import CandidateRequiredMixin

from .forms import CandidateProfileForm
from .models import CandidateProfile


class ProfileUpdateView(CandidateRequiredMixin, UpdateView):
    form_class = CandidateProfileForm
    template_name = "candidates/profile_form.html"
    success_url = reverse_lazy("candidates:profile")

    def get_object(self, queryset=None):
        return CandidateProfile.for_user(self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "Profile saved.")
        return super().form_valid(form)
