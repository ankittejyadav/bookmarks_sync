import time
import subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from bookmarks_import import import_bookmarks


# Helper to check if Chrome is running on Windows
def chrome_is_running():
    proc = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq chrome.exe"], capture_output=True, text=True
    )
    return "chrome.exe" in proc.stdout


class ImportChangeHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_import_time = 0

    def on_modified(self, event):
        # Only react to our synced JSON file
        if not event.src_path.endswith("Bookmarks_Chrome.json"):
            return

        # Debounce: only run once per actual file update
        mtime = Path(event.src_path).stat().st_mtime
        if mtime == self.last_import_time:
            return
        self.last_import_time = mtime

        print("🔔 Detected new synced bookmarks")

        # Wait until Chrome is closed
        while chrome_is_running():
            print("⏳ Chrome is open, delaying import for 10s…")
            time.sleep(10)

        print("📥 Chrome closed—importing now!")
        import_bookmarks(event.src_path)


def git_pull_changes():
    try:
        subprocess.run(["git", "pull"], check=True)
        print("⬇️ Pulled latest from GitHub")
    except subprocess.CalledProcessError as e:
        print(f"❌ Git pull failed: {e}")


if __name__ == "__main__":
    # Path to the synced export JSON
    bookmarks_file = Path.cwd() / "exported_bookmarks" / "Bookmarks_Chrome.json"
    bookmarks_dir = bookmarks_file.parent

    # Set up the file watcher
    event_handler = ImportChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, path=str(bookmarks_dir), recursive=False)

    print(f"👀 Watching for synced file changes in: {bookmarks_dir}")
    observer.start()

    try:
        # Periodically pull from GitHub
        while True:
            git_pull_changes()
            time.sleep(30)  # Pull every 30 seconds
    except KeyboardInterrupt:
        observer.stop()

    observer.join()
