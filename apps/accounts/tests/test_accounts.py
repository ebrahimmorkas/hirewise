import pytest
from django.http import HttpResponse
from django.test import RequestFactory
from django.urls import reverse
from django.views import View

from apps.accounts.mixins import EmployerRequiredMixin
from apps.accounts.models import User
from apps.accounts.tests.factories import DEFAULT_PASSWORD, CandidateFactory, EmployerFactory

pytestmark = pytest.mark.django_db


def test_signup_as_employer(client):
    response = client.post(
        reverse("signup"),
        {
            "full_name": "Grace Hopper",
            "email": "Grace@Example.com",
            "role": "employer",
            "password1": DEFAULT_PASSWORD,
            "password2": DEFAULT_PASSWORD,
        },
        follow=True,
    )

    user = User.objects.get()
    assert user.email == "grace@example.com"
    assert user.is_employer
    assert response.context["user"].is_authenticated


def test_signup_prefills_role_from_query(client):
    response = client.get(reverse("signup"), {"role": "employer"})

    assert response.context["form"].initial["role"] == "employer"


def test_signup_rejects_duplicate_email(client):
    CandidateFactory(email="taken@example.com")

    response = client.post(
        reverse("signup"),
        {
            "full_name": "X",
            "email": "TAKEN@example.com",
            "role": "candidate",
            "password1": DEFAULT_PASSWORD,
            "password2": DEFAULT_PASSWORD,
        },
    )

    assert "email" in response.context["form"].errors


class EmployerOnly(EmployerRequiredMixin, View):
    def get(self, request):
        return HttpResponse("ok")


def test_role_mixin_allows_matching_role():
    request = RequestFactory().get("/")
    request.user = EmployerFactory()

    assert EmployerOnly.as_view()(request).status_code == 200


def test_role_mixin_forbids_other_role():
    from django.core.exceptions import PermissionDenied

    request = RequestFactory().get("/")
    request.user = CandidateFactory()

    with pytest.raises(PermissionDenied):
        EmployerOnly.as_view()(request)


def test_role_mixin_redirects_anonymous(client):
    from django.contrib.auth.models import AnonymousUser

    request = RequestFactory().get("/private/")
    request.user = AnonymousUser()

    response = EmployerOnly.as_view()(request)

    assert response.status_code == 302
    assert reverse("login") in response.url
