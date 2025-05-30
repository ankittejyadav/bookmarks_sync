import time
import subprocess
import hashlib
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from bookmarks_import import import_bookmarks


def chrome_is_running():
    proc = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq chrome.exe"], capture_output=True, text=True
    )
    return "chrome.exe" in proc.stdout


def get_checksum(path):
    try:
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except FileNotFoundError:
        return None


class ImportChangeHandler(FileSystemEventHandler):
    def __init__(self, bookmarks_file):
        self.bookmarks_file = Path(bookmarks_file)
        self.last_checksum = get_checksum(self.bookmarks_file)

    def on_modified(self, event):
        if Path(event.src_path) != self.bookmarks_file:
            return

        current_checksum = get_checksum(self.bookmarks_file)
        if current_checksum == self.last_checksum:
            return  # No real change
        self.last_checksum = current_checksum

        print("🔔 Detected new synced bookmarks")

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
    bookmarks_file = Path.cwd() / "exported_bookmarks" / "Bookmarks_Chrome.json"
    bookmarks_dir = bookmarks_file.parent

    event_handler = ImportChangeHandler(bookmarks_file)
    observer = Observer()
    observer.schedule(event_handler, path=str(bookmarks_dir), recursive=False)

    print(f"👀 Watching for synced file changes in: {bookmarks_dir}")
    observer.start()

    try:
        while True:
            git_pull_changes()
            time.sleep(30)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()
