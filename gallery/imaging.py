import io
import warnings

from django.core.exceptions import ValidationError
from PIL import Image, ImageOps, UnidentifiedImageError

Image.MAX_IMAGE_PIXELS = 40_000_000
FORMATS = {
    "JPEG": ("jpg", "image/jpeg"),
    "PNG": ("png", "image/png"),
    "WEBP": ("webp", "image/webp"),
    "GIF": ("gif", "image/gif"),
    "BMP": ("bmp", "image/bmp"),
    "TIFF": ("tiff", "image/tiff"),
}


def inspect_image(upload):
    if upload.size > 25 * 1024 * 1024:
        raise ValidationError("Each image must be 25 MB or smaller.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(upload) as source:
                fmt = source.format
                if fmt not in FORMATS:
                    raise ValidationError("Use PNG, JPG, WebP, GIF, BMP or TIFF images.")
                source.verify()
            upload.seek(0)
            with Image.open(upload) as source:
                picture = ImageOps.exif_transpose(source).convert("RGBA")
                width, height = picture.size
                if width * height > 40_000_000:
                    raise ValidationError("Images must be 40 megapixels or smaller.")
                # Preview the first frame while preserving the original upload.
                background = Image.new("RGB", picture.size, "#faf9f6")
                background.paste(picture, mask=picture.getchannel("A"))
                background.thumbnail((1200, 1200))
                output = io.BytesIO()
                background.save(output, "WEBP", quality=85)
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        SyntaxError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise ValidationError("This image is damaged, unsupported, or too large to process.") from exc
    finally:
        upload.seek(0)
    return {
        "extension": FORMATS[fmt][0],
        "mime_type": FORMATS[fmt][1],
        "width": width,
        "height": height,
        "thumbnail": output.getvalue(),
    }
