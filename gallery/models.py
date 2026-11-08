import uuid

from django.conf import settings
from django.db import models


class Folder(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=80)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["owner", "name"], name="unique_folder_per_owner")]


class Tag(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=40)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["owner", "name"], name="unique_tag_per_owner")]


class Reference(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    folder = models.ForeignKey(
        Folder, null=True, blank=True, on_delete=models.SET_NULL, related_name="images"
    )
    title = models.CharField(max_length=180)
    original = models.FileField(upload_to="originals/%Y/%m/")
    thumbnail = models.FileField(upload_to="thumbnails/%Y/%m/")
    mime_type = models.CharField(max_length=40)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    size = models.PositiveBigIntegerField()
    tags = models.ManyToManyField(Tag, blank=True, related_name="images")
    notes = models.TextField(blank=True, max_length=4000)
    favorite = models.BooleanField(default=False)
    trashed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["owner", "trashed", "-created_at"])]
