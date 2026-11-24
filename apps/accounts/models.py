from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Login identity for RepairDesk staff."""

    class Role(models.TextChoices):
        ADMINISTRATOR = "administrator", "Administrator"
        TECHNICIAN = "technician", "Technician"

    role = models.CharField(
        max_length=32,
        choices=Role.choices,
        default=Role.ADMINISTRATOR,
    )
    phone = models.CharField(max_length=20, blank=True)
    display_name = models.CharField(max_length=150, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(role__in=["administrator", "technician"]),
                name="accounts_user_role_valid",
            )
        ]

    @property
    def is_administrator(self):
        """Returns True if the user has administrator privileges."""
        return self.role == self.Role.ADMINISTRATOR or self.is_superuser

    @property
    def is_technician(self):
        """Returns True if the user is designated as a technician."""
        return self.role == self.Role.TECHNICIAN

    def __str__(self):
        return self.display_name or self.username
