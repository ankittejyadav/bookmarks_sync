import time
import subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from bookmarks_export import export_bookmarks, get_chrome_bookmarks_path
from lock_utils import set_lock, clear_lock, is_locked

# How long to hold the lock (seconds)
LOCK_HOLD = 5


class BookmarkChangeHandler(FileSystemEventHandler):
    def __init__(self, export_dir):
        self.export_dir = Path(export_dir)

    def on_modified(self, event):
        # Only fire on Chrome's Bookmarks file
        if not event.src_path.endswith("Bookmarks"):
            return

        if is_locked():
            print("🔒 Export skipped (lock active)")
            return

        print("📌 Bookmark change detected → Exporting & Pushing")
        set_lock()

        # Perform export and git push
        export_bookmarks(self.export_dir)
        subprocess.run(["git", "add", "."], check=False)
        subprocess.run(["git", "commit", "-m", "🔁 Auto-sync export"], check=False)
        subprocess.run(["git", "push"], check=False)
        print("🚀 Export pushed to GitHub")

        # Keep the lock for a short window to avoid loops
        time.sleep(LOCK_HOLD)
        clear_lock()
        print("🔓 Export lock cleared")


if __name__ == "__main__":
    export_dir = Path.cwd() / "exported_bookmarks"
    bookmarks_dir = get_chrome_bookmarks_path().parent

    handler = BookmarkChangeHandler(export_dir)
    observer = Observer()
    observer.schedule(handler, str(bookmarks_dir), recursive=False)

    print(f"👀 Watching Chrome bookmarks in: {bookmarks_dir}")
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
