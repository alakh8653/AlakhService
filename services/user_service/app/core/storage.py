"""Where profile photos are kept: a local directory (a mounted volume in production, included in backups).

Files are named by a random id, never by anything the client sent, and their type is taken from their
first bytes, so a script renamed to .png is refused. Keys look like "<user folder>/<uuid>.<ext>"; the
folder is derived from the user id so that no id can reach outside the root.
"""

import os
import uuid
from pathlib import Path
from typing import Optional

from app.config import settings

# Content type -> (file extension, the bytes such a file starts with).
ALLOWED_TYPES = {
    "image/jpeg": ("jpg", (b"\xff\xd8\xff",)),
    "image/png": ("png", (b"\x89PNG\r\n\x1a\n",)),
    "image/webp": ("webp", (b"RIFF",)),
}
CONTENT_TYPE_BY_EXT = {ext: content_type for content_type, (ext, _) in ALLOWED_TYPES.items()}


class StorageDisabled(Exception):
    pass


def sniff_content_type(data: bytes, declared: Optional[str]) -> Optional[str]:
    """The declared type when the file really is one; None for anything else."""
    declared = (declared or "").split(";")[0].strip().lower()
    if declared not in ALLOWED_TYPES:
        return None
    _, magics = ALLOWED_TYPES[declared]
    if not any(data.startswith(m) for m in magics):
        return None
    if declared == "image/webp" and data[8:12] != b"WEBP":
        return None
    return declared


def user_folder(user_id: str) -> str:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"avatar:{user_id}").hex


class LocalAvatarStorage:
    def __init__(self, root: str):
        self.root = Path(root) if root else None

    @property
    def enabled(self) -> bool:
        return self.root is not None

    def _path(self, key: str) -> Path:
        if self.root is None:
            raise StorageDisabled()
        path = (self.root / key).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError("Invalid storage key")
        return path

    def save(self, user_id: str, data: bytes, content_type: str) -> str:
        ext = ALLOWED_TYPES[content_type][0]
        key = f"{user_folder(user_id)}/{uuid.uuid4()}.{ext}"
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
        return key

    def path_of(self, key: str) -> Path:
        return self._path(key)

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink(missing_ok=True)
        except (StorageDisabled, ValueError, OSError):
            pass

    def delete_user(self, user_id: str) -> None:
        """Every photo the user ever uploaded (account deletion)."""
        try:
            folder = self._path(user_folder(user_id) + "/x").parent
        except (StorageDisabled, ValueError):
            return
        for path in folder.glob("*"):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        try:
            folder.rmdir()
        except OSError:
            pass


def get_storage() -> LocalAvatarStorage:
    return LocalAvatarStorage(settings.AVATAR_STORAGE_DIR)
