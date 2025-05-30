import time
import subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from bookmarks_export import export_bookmarks, get_chrome_bookmarks_path

# suppression window in seconds
SUPPRESS_AFTER_IMPORT = 5
last_import_time = 0


def git_push_changes():
    subprocess.run(["git", "add", "."], check=False)
    subprocess.run(["git", "commit", "-m", "🔁 Auto-sync new bookmark"], check=False)
    subprocess.run(["git", "push"], check=False)
    print("🚀 Pushed to GitHub")


class BookmarkChangeHandler(FileSystemEventHandler):
    def __init__(self, export_dir):
        self.export_dir = Path(export_dir)

    def on_modified(self, event):
        global last_import_time
        now = time.time()
        # skip if we just imported
        if now - last_import_time < SUPPRESS_AFTER_IMPORT:
            return

        if event.src_path.endswith("Bookmarks"):
            print("📌 Detected Chrome bookmark change, exporting…")
            export_bookmarks(self.export_dir)
            git_push_changes()


if __name__ == "__main__":
    export_dir = Path.cwd() / "exported_bookmarks"
    bookmarks_path = get_chrome_bookmarks_path().parent

    handler = BookmarkChangeHandler(export_dir)
    obs = Observer()
    obs.schedule(handler, str(bookmarks_path), recursive=False)

    print(f"👀 Watching Chrome bookmarks in: {bookmarks_path}")
    obs.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        obs.stop()
    obs.join()
