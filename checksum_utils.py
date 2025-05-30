# checksum_utils.py
import hashlib
from pathlib import Path


def calc_checksum(path: Path) -> str:
    """Return SHA256 checksum of a file."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        hasher.update(f.read())
    return hasher.hexdigest()


def read_last(path: Path) -> str:
    """Read stored checksum (or return empty if not exist)."""
    if path.exists():
        return path.read_text().strip()
    return ""


def write_last(path: Path, checksum: str):
    """Write checksum to file (creating parent dirs)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(checksum)
