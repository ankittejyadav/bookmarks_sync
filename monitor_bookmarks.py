import time
import subprocess
import hashlib
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from bookmarks_export import export_bookmarks, get_chrome_bookmarks_path


def get_checksum(path):
    try:
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except FileNotFoundError:
        return None


class BookmarkChangeHandler(FileSystemEventHandler):
    def __init__(self, export_dir):
        self.export_dir = Path(export_dir)
        self.bookmarks_path = get_chrome_bookmarks_path()
        self.last_checksum = get_checksum(self.bookmarks_path)

    def on_any_event(self, event):
        if event.is_directory:
            return

        if any(
            event.src_path.endswith(name) for name in ["Bookmarks", "Bookmarks-journal"]
        ):
            current_checksum = get_checksum(self.bookmarks_path)
            if current_checksum == self.last_checksum:
                return  # No real change
            self.last_checksum = current_checksum

            print("📌 Bookmarks file event detected, exporting...")
            export_bookmarks(self.export_dir)
            git_push_changes()


def git_push_changes():
    try:
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", "🔁 Auto-sync new bookmark"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("🚀 Pushed to GitHub")
    except subprocess.CalledProcessError as e:
        if "nothing to commit" in str(e):
            print("ℹ️ No new changes to commit")
        else:
            print(f"❌ Git push failed: {e}")


if __name__ == "__main__":
    bookmarks_path = get_chrome_bookmarks_path()
    folder_to_watch = bookmarks_path.parent
    export_dir = Path.cwd() / "exported_bookmarks"

    event_handler = BookmarkChangeHandler(export_dir)
    observer = Observer()
    observer.schedule(event_handler, path=str(folder_to_watch), recursive=True)

    print(f"👀 Watching for changes in: {folder_to_watch}")
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()
