import io
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .imaging import inspect_image
from .models import Folder, Reference, Tag


def picture(fmt="PNG", name=None):
    stream = io.BytesIO()
    Image.new("RGB", (64, 48), "#668080").save(stream, fmt)
    return SimpleUploadedFile(
        name or "study." + fmt.lower(), stream.getvalue(), content_type="image/" + fmt.lower()
    )


class LibraryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("artist", password="Test-only-strong-pass-982")
        cls.other = User.objects.create_user("other", password="Test-only-strong-pass-983")
        cls.folder = Folder.objects.create(owner=cls.owner, name="Anatomy")
        cls.foreign_folder = Folder.objects.create(owner=cls.other, name="Private folder")

    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(
            MEDIA_ROOT=self.media.name,
            STORAGES={
                "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
            },
        )
        self.settings_override.enable()
        self.addCleanup(self.media.cleanup)
        self.addCleanup(self.settings_override.disable)
        self.client.force_login(self.owner)

    def upload(self, **kwargs):
        return self.client.post(reverse("upload"), {"image": picture(), **kwargs})

    def reference(self):
        response = self.upload(folder=self.folder.pk, tags="#Anatomy, #hands")
        self.assertEqual(response.status_code, 201)
        return Reference.objects.get(pk=response.json()["id"])

    def test_supported_formats_preserve_original_bytes(self):
        for fmt in ("PNG", "JPEG", "WEBP", "GIF", "BMP", "TIFF"):
            with self.subTest(fmt=fmt):
                file = picture(fmt)
                original = file.read()
                file.seek(0)
                response = self.client.post(reverse("upload"), {"image": file})
                self.assertEqual(response.status_code, 201)
                ref = Reference.objects.get(pk=response.json()["id"])
                with ref.original.open("rb") as stored:
                    self.assertEqual(stored.read(), original)
                with ref.thumbnail.open("rb") as thumb:
                    self.assertEqual(Image.open(thumb).format, "WEBP")

    def test_upload_creates_owned_tags_and_folder(self):
        ref = self.reference()
        self.assertEqual(ref.owner, self.owner)
        self.assertEqual(ref.folder, self.folder)
        self.assertEqual(set(ref.tags.values_list("name", flat=True)), {"anatomy", "hands"})
        self.assertFalse(Tag.objects.exclude(owner=self.owner).exists())

    def test_reject_foreign_folder_without_writing_file(self):
        response = self.upload(folder=self.foreign_folder.pk)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Reference.objects.count(), 0)
        self.assertEqual(list(Path(self.media.name).rglob("*")), [])

    def test_reject_invalid_tags_before_writing(self):
        response = self.upload(tags="#<script>")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Reference.objects.count(), 0)

    def test_reject_non_image_and_svg(self):
        for content in (b"not an image", b'<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>'):
            response = self.client.post(
                reverse("upload"), {"image": SimpleUploadedFile("evil.png", content, "image/png")}
            )
            self.assertEqual(response.status_code, 400)
        self.assertEqual(Reference.objects.count(), 0)

    def test_missing_file_is_clear_error(self):
        self.assertEqual(self.client.post(reverse("upload")).status_code, 400)

    def test_actual_format_wins_over_filename_and_mime(self):
        file = picture("PNG", "disguised.html")
        file.content_type = "text/html"
        response = self.client.post(reverse("upload"), {"image": file})
        ref = Reference.objects.get(pk=response.json()["id"])
        self.assertEqual(ref.mime_type, "image/png")
        self.assertTrue(ref.original.name.endswith(".png"))

    def test_size_limit(self):
        file = picture()
        file.size = 26 * 1024 * 1024
        with self.assertRaisesMessage(ValidationError, "25 MB"):
            inspect_image(file)

    def test_pixel_bomb_rejected(self):
        with patch("PIL.Image.MAX_IMAGE_PIXELS", 10):
            with self.assertRaises(ValidationError):
                inspect_image(picture())

    def test_failed_database_write_cleans_storage(self):
        with patch.object(Reference, "save", side_effect=RuntimeError("simulated database failure")):
            with self.assertRaises(RuntimeError):
                self.upload()
        self.assertFalse(any(p.is_file() for p in Path(self.media.name).rglob("*")))

    def test_other_user_cannot_read_or_change_reference(self):
        ref = self.reference()
        self.client.force_login(self.other)
        for variant in ("original", "thumbnail", "download"):
            self.assertEqual(self.client.get(reverse("image_file", args=[ref.pk, variant])).status_code, 404)
        self.assertEqual(self.client.get(reverse("detail", args=[ref.pk])).status_code, 404)
        self.assertEqual(
            self.client.post(reverse("image_edit", args=[ref.pk]), {"title": "stolen"}).status_code, 404
        )
        self.assertEqual(
            self.client.post(reverse("image_state", args=[ref.pk]), {"action": "trash"}).status_code, 404
        )

    def test_other_user_cannot_modify_folder(self):
        self.client.force_login(self.other)
        self.assertEqual(
            self.client.post(reverse("folder_edit", args=[self.folder.pk]), {"action": "delete"}).status_code,
            404,
        )
        self.assertEqual(self.client.get("/", {"folder": self.folder.pk}).status_code, 404)

    def test_logged_out_cannot_access_images(self):
        ref = self.reference()
        self.client.logout()
        for variant in ("original", "thumbnail", "download"):
            self.assertEqual(self.client.get(reverse("image_file", args=[ref.pk, variant])).status_code, 302)
        self.assertEqual(self.upload().status_code, 302)

    def test_private_download_headers(self):
        ref = self.reference()
        response = self.client.get(reverse("image_file", args=[ref.pk, "download"]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertTrue(response["Content-Disposition"].startswith("attachment;"))
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        response.close()

    def test_csrf_required_on_mutations(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(reverse("folder_create"), {"name": "Attack"}).status_code, 403)
        self.assertEqual(client.post(reverse("upload"), {"image": picture()}).status_code, 403)

    def test_search_by_exact_tag_and_title(self):
        self.reference()
        for query in ("#anatomy", "#ANATOMY", "study", "hands"):
            response = self.client.get("/", {"q": query})
            self.assertEqual(response.context["page"].paginator.count, 1)
        self.assertEqual(self.client.get("/", {"q": "#anat"}).context["page"].paginator.count, 0)

    def test_library_is_account_scoped(self):
        self.reference()
        self.client.force_login(self.other)
        response = self.client.get("/")
        self.assertEqual(response.context["total"], 0)
        self.assertEqual(response.context["page"].paginator.count, 0)
        self.assertEqual(list(response.context["tags"]), [])

    def test_move_and_edit_tags(self):
        ref = self.reference()
        new_folder = Folder.objects.create(owner=self.owner, name="Lighting")
        response = self.client.post(
            reverse("image_edit", args=[ref.pk]),
            {
                "title": "Window study",
                "folder": new_folder.pk,
                "notes": "Soft light",
                "tag_names": "#light #Light #warm",
            },
        )
        self.assertEqual(response.status_code, 302)
        ref.refresh_from_db()
        self.assertEqual(ref.folder, new_folder)
        self.assertEqual(ref.title, "Window study")
        self.assertEqual(set(ref.tags.values_list("name", flat=True)), {"light", "warm"})

    def test_edit_rejects_foreign_folder(self):
        ref = self.reference()
        response = self.client.post(
            reverse("image_edit", args=[ref.pk]), {"title": "No", "folder": self.foreign_folder.pk}
        )
        self.assertEqual(response.status_code, 400)
        ref.refresh_from_db()
        self.assertEqual(ref.folder, self.folder)

    def test_folder_delete_keeps_references(self):
        ref = self.reference()
        self.client.post(reverse("folder_edit", args=[self.folder.pk]), {"action": "delete"})
        ref.refresh_from_db()
        self.assertIsNone(ref.folder)
        self.assertTrue(Path(ref.original.path).exists())

    def test_folder_create_and_rename(self):
        self.client.post(reverse("folder_create"), {"name": "Textures"})
        folder = Folder.objects.get(owner=self.owner, name="Textures")
        self.client.post(reverse("folder_edit", args=[folder.pk]), {"name": "Materials"})
        folder.refresh_from_db()
        self.assertEqual(folder.name, "Materials")
        self.client.post(reverse("folder_edit", args=[folder.pk]), {"name": "Anatomy"})
        folder.refresh_from_db()
        self.assertEqual(folder.name, "Materials")

    def test_favorite_trash_restore(self):
        ref = self.reference()
        url = reverse("image_state", args=[ref.pk])
        self.client.post(url, {"action": "favorite"})
        self.assertEqual(self.client.get("/", {"view": "favorites"}).context["page"].paginator.count, 1)
        self.client.post(url, {"action": "trash"})
        self.assertEqual(self.client.get("/").context["total"], 0)
        self.assertEqual(self.client.get("/", {"view": "trash"}).context["page"].paginator.count, 1)
        self.client.post(url, {"action": "restore"})
        self.assertEqual(self.client.get("/").context["total"], 1)
        self.assertTrue(Path(ref.original.path).exists())

    def test_custom_tags_creation(self):
        self.client.post(reverse("tag_create"), {"name": "#My-Tag anatomy, anatomy"})
        self.assertEqual(
            set(Tag.objects.filter(owner=self.owner).values_list("name", flat=True)), {"my-tag", "anatomy"}
        )

    def test_mutations_require_post(self):
        ref = self.reference()
        for url in (
            reverse("folder_create"),
            reverse("upload"),
            reverse("image_state", args=[ref.pk]),
            reverse("image_edit", args=[ref.pk]),
            reverse("logout"),
        ):
            self.assertEqual(self.client.get(url).status_code, 405)

    def test_html_titles_are_escaped(self):
        ref = self.reference()
        ref.title = "<script>alert(1)</script>"
        ref.save()
        response = self.client.get("/")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotContains(response, "<script>alert(1)</script>")

    def test_signup_login_and_persistence(self):
        self.client.logout()
        response = self.client.post(
            reverse("signup"),
            {
                "username": "NewArtist",
                "password1": "Test-only-strong-pass-991",
                "password2": "Test-only-strong-pass-991",
            },
        )
        self.assertEqual(response.status_code, 302)
        response = self.upload()
        self.assertEqual(response.status_code, 201)
        self.client.post(reverse("logout"))
        self.assertEqual(
            self.client.post(
                reverse("login"), {"username": "newartist", "password": "Test-only-strong-pass-991"}
            ).status_code,
            302,
        )
        self.assertEqual(self.client.get("/").context["total"], 1)

    def test_weak_password_and_case_duplicate_rejected(self):
        self.client.logout()
        for username, password in [("unique", "12345678"), ("ARTIST", "Test-only-strong-pass-991")]:
            self.assertEqual(
                self.client.post(
                    reverse("signup"), {"username": username, "password1": password, "password2": password}
                ).status_code,
                200,
            )
        self.assertEqual(User.objects.count(), 2)

    def test_guest_gallery_is_separate_from_account(self):
        self.client.logout()
        response = self.client.get("/")
        self.assertContains(response, "sample collection")
        self.assertEqual(len(response.context["artworks"]), 8)
        self.assertEqual(Reference.objects.count(), 0)
