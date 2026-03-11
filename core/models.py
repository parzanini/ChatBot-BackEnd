import secrets

from django.conf import settings
from django.db import models


def _generate_token_key():
    return secrets.token_hex(32)


class AuthToken(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="auth_tokens")
    key = models.CharField(max_length=64, unique=True, db_index=True, default=_generate_token_key)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user_id}:{self.key[:8]}"


class IndexDatabaseRun(models.Model):
    success = models.BooleanField(default=False)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        status = "OK" if self.success else "ERROR"
        return f"{status}:{self.created_at.isoformat()}"
