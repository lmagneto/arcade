from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        PLATFORM_ADMIN = "PLATFORM_ADMIN", "Platform Administrator"
        MAJOR_OWNER = "MAJOR_OWNER", "Major Account Owner"
        PLAYER = "PLAYER", "Player"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.PLAYER,
    )

    must_change_password = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.username} ({self.role})"
