from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Document(models.Model):
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True, default='')
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='owned_documents',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.title


class DocumentShare(models.Model):
    class Permission(models.TextChoices):
        VIEWER = 'viewer', 'Viewer'
        EDITOR = 'editor', 'Editor'

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='shares',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='document_shares',
    )
    permission = models.CharField(
        max_length=10,
        choices=Permission.choices,
        default=Permission.VIEWER,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['document', 'user'],
                name='unique_document_user_share',
            )
        ]

    def clean(self):
        super().clean()
        if self.document_id and self.user_id:
            if self.document.owner_id == self.user_id:
                raise ValidationError("The document owner cannot be added as a share.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.document.title} - {self.user.username} ({self.permission})"
