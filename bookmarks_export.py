# bookmark_sync.py
import os
import shutil
import platform
from datetime import datetime
from pathlib import Path
import time


def wait_for_file_access(file_path, timeout=10):
    file_path = Path(file_path)
    start = time.time()
    while time.time() - start < timeout:
        try:
            with open(file_path, "rb"):
                return True
        except (PermissionError, OSError):
            time.sleep(0.5)
    raise Exception(f"❌ Timeout: Cannot access file {file_path}")


def get_chrome_bookmarks_path():
    system = platform.system()
    if system == "Windows":
        return (
            Path(os.environ["LOCALAPPDATA"])
            / "Google/Chrome/User Data/Default/Bookmarks"
        )
    elif system == "Darwin":
        return (
            Path.home() / "Library/Application Support/Google/Chrome/Default/Bookmarks"
        )
    else:
        raise Exception("Unsupported OS")


def export_bookmarks(export_path):
    bookmarks_file = get_chrome_bookmarks_path()
    wait_for_file_access(bookmarks_file)  # Wait for file to be free

    export_path = Path(export_path).expanduser()
    export_path.mkdir(parents=True, exist_ok=True)
    export_file = export_path / "Bookmarks_Chrome.json"

    shutil.copy2(bookmarks_file, export_file)
    print(f"✅ Exported: {export_file}")
    return export_file


if __name__ == "__main__":
    # Default export location (you can change this)
    export_dir = Path.cwd() / "exported_bookmarks"
    export_bookmarks(export_dir)
