"""User domain.

We use a custom User with email-as-username and a role enum so that the same
account can switch between investor / owner / admin behaviors without forking
the auth pipeline.
"""

from __future__ import annotations

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class Role(models.TextChoices):
    INVESTOR = "investor", "Investor"
    OWNER = "owner", "Owner / Agency"
    ADMIN = "admin", "Admin"


class UserManager(BaseUserManager):
    """Email-as-username manager."""

    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra):
        if not email:
            raise ValueError("Users require an email address.")
        email = self.normalize_email(email)
        user = self.model(email=email, username=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email: str, password: str | None = None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("role", Role.ADMIN)
        if not extra.get("is_staff") or not extra.get("is_superuser"):
            raise ValueError("Superuser must have is_staff and is_superuser set.")
        return self._create_user(email, password, **extra)


class User(AbstractUser):
    email = models.EmailField(unique=True, db_index=True)
    role = models.CharField(
        max_length=16, choices=Role.choices, default=Role.INVESTOR, db_index=True
    )
    company_name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    country = models.CharField(max_length=2, blank=True, help_text="ISO-3166-1 alpha-2")
    email_verified = models.BooleanField(
        default=False,
        help_text="True once the user clicked the verification link sent at signup.",
    )
    email_verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.email

    @property
    def is_owner(self) -> bool:
        return self.role == Role.OWNER

    @property
    def is_investor(self) -> bool:
        return self.role == Role.INVESTOR
