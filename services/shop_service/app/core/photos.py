"""Makes an uploaded photo safe to show to anyone.

A phone photo carries where and when it was taken, and a provider's work photos are often taken in customers'
homes. So nothing is kept as uploaded: the picture is decoded and saved again as a new JPEG, which leaves all of
that behind, and any script hidden in the file with it. It is also made smaller, to load well on mobile data.
"""

import io

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_SIDE = 1600
QUALITY = 80
# Far above any phone camera. A file claiming more is an attack on memory, not a photo.
MAX_PIXELS = 60_000_000
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


class NotAPhoto(Exception):
    pass


def clean_photo(data: bytes) -> bytes:
    """The photo as a new JPEG with no metadata, upright, at most MAX_SIDE. Raises NotAPhoto for anything else."""
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in ALLOWED_FORMATS or image.width * image.height > MAX_PIXELS:
                raise NotAPhoto()
            image.load()
            # The camera's rotation lives in the metadata about to go.
            upright = ImageOps.exif_transpose(image).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as e:
        raise NotAPhoto() from e
    upright.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    upright.save(out, "JPEG", quality=QUALITY, optimize=True)
    return out.getvalue()
