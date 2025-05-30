# bookmarks_import.py
import os
import shutil
import platform
from datetime import datetime
from pathlib import Path


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


def import_bookmarks(import_file):
    import_file = Path(import_file).expanduser()
    if not import_file.exists():
        print(f"❌ Import file not found: {import_file}")
        return

    bookmarks_file = get_chrome_bookmarks_path()

    # Replace with synced bookmarks
    shutil.copy2(import_file, bookmarks_file)
    print(f"✅ Imported bookmarks from: {import_file}")


if __name__ == "__main__":
    # Default path to synced bookmark file
    import_file = Path.cwd() / "exported_bookmarks" / "Bookmarks_Chrome.json"
    import_bookmarks(import_file)
