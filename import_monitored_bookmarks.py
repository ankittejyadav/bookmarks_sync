import time
import subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from bookmarks_import import import_bookmarks
from lock_utils import set_lock, clear_lock, is_locked

# How long to hold the lock (seconds)
LOCK_HOLD = 5


class ImportChangeHandler(FileSystemEventHandler):
    def __init__(self, json_path):
        self.json_path = Path(json_path)

    def on_modified(self, event):
        if not event.src_path.endswith(self.json_path.name):
            return

        if is_locked():
            print("🔒 Import skipped (lock active)")
            return

        print("📥 Synced JSON change detected → Pulling & Importing")
        set_lock()

        # Pull & import
        subprocess.run(["git", "pull"], check=False)
        print("⬇️ Pulled latest from GitHub")
        # Delay until Chrome is closed
        while (
            subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq chrome.exe"],
                capture_output=True,
                text=True,
            ).stdout.find("chrome.exe")
            != -1
        ):
            print("⏳ Chrome is open, delaying import…")
            time.sleep(5)

        import_bookmarks(self.json_path)
        print("✅ Import complete")

        # Hold lock briefly, then clear
        time.sleep(LOCK_HOLD)
        clear_lock()
        print("🔓 Import lock cleared")


if __name__ == "__main__":
    json_file = Path.cwd() / "exported_bookmarks" / "Bookmarks_Chrome.json"
    handler = ImportChangeHandler(json_file)
    observer = Observer()
    observer.schedule(handler, str(json_file.parent), recursive=False)

    print(f"👀 Watching exported JSON in: {json_file.parent}")
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
