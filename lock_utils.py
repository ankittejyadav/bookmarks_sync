# lock_utils.py
from pathlib import Path

LOCK_FILE = Path.cwd() / "sync.lock"


def set_lock():
    """Create the lock file."""
    LOCK_FILE.write_text("locked")


def clear_lock():
    """Remove the lock file."""
    if LOCK_FILE.exists():
        LOCK_FILE.unlink()


def is_locked():
    """Check whether lock is active."""
    return LOCK_FILE.exists()
