from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def absolute(path: str) -> str:
    return f"{settings.SITE_URL.rstrip('/')}{path}"


def send(template: str, subject: str, to: str, context: dict, headers: dict | None = None):
    body = render_to_string(f"notifications/email/{template}.txt", context)
    message = EmailMultiAlternatives(
        subject, body, settings.DEFAULT_FROM_EMAIL, [to], headers=headers or {}
    )
    message.send()
