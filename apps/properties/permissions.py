from __future__ import annotations

from rest_framework import permissions


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Owners can edit their own properties; everyone else is read-only."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.user.is_staff:
            return True
        return obj.owner_id == request.user.id
