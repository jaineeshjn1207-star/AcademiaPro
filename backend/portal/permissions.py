from rest_framework import permissions

BLOCKED_MESSAGE = "ACCOUNT_BLOCKED: Your account has been locked following a suspected unfair-means violation during an exam. You cannot sign back in until your faculty restores access."


class IsFaculty(permissions.BasePermission):
    """
    Custom permission to only allow faculty users to access API.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (request.user.user_type in ('faculty', 'admin') or request.user.is_staff or request.user.is_superuser))


class IsStudent(permissions.BasePermission):
    """
    Custom permission to only allow student users. A student whose account
    has been locked for unfair means is rejected on every request, not just
    at login — this is what makes the lock take effect immediately even on
    an already-issued access token.
    """
    message = BLOCKED_MESSAGE

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.user_type == 'student'):
            return False
        if user.is_blocked:
            return False
        return True




class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (getattr(user, 'user_type', None) == 'admin' or user.is_staff or user.is_superuser))
