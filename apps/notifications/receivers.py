from django.dispatch import receiver

from apps.applications.signals import application_status_changed, application_submitted

from .tasks import notify_employer_of_application, notify_status_change


@receiver(application_submitted, dispatch_uid="notifications.application_submitted")
def on_application_submitted(sender, application, **kwargs) -> None:
    notify_employer_of_application.delay(application.pk)


@receiver(application_status_changed, dispatch_uid="notifications.status_changed")
def on_status_changed(sender, application, from_status, to_status, **kwargs) -> None:
    notify_status_change.delay(application.pk, from_status, to_status)
