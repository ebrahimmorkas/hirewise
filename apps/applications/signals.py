"""Domain events (sent after the transaction commits)."""

from django.dispatch import Signal

# kwargs: application
application_submitted = Signal()

# kwargs: application, from_status, to_status
application_status_changed = Signal()
