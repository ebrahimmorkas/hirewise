from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import CreateView

from .forms import SignUpForm


class SignUpView(CreateView):
    form_class = SignUpForm
    template_name = "accounts/signup.html"

    def get_initial(self):
        role = self.request.GET.get("role")
        return {"role": role} if role in {"candidate", "employer"} else {}

    def form_valid(self, form):
        user = form.save()
        login(self.request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(self.request, f"Welcome to HireWise, {user.get_short_name()}!")
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse("home")
