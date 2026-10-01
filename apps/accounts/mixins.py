from django.contrib.auth.mixins import AccessMixin


class RoleRequiredMixin(AccessMixin):
    """Restrict a view to authenticated users with a given role."""

    required_role: str = ""
    permission_denied_message = "This page is not available for your account type."

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.role != self.required_role:
            self.raise_exception = True
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)


class CandidateRequiredMixin(RoleRequiredMixin):
    required_role = "candidate"


class EmployerRequiredMixin(RoleRequiredMixin):
    required_role = "employer"
