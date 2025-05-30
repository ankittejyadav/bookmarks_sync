import time
import subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from bookmarks_import import import_bookmarks


class ImportChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith("Bookmarks_Chrome.json"):
            print("📥 Synced bookmarks changed, importing...")
            import_bookmarks(event.src_path)


def git_pull_changes():
    try:
        subprocess.run(["git", "pull"], check=True)
        print("📥 Pulled latest from GitHub")
    except subprocess.CalledProcessError as e:
        print(f"❌ Git pull failed: {e}")


if __name__ == "__main__":
    bookmarks_file = Path.cwd() / "exported_bookmarks" / "Bookmarks_Chrome.json"
    bookmarks_dir = bookmarks_file.parent

    event_handler = ImportChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, path=str(bookmarks_dir), recursive=False)

    print(f"👀 Watching for synced file changes in: {bookmarks_dir}")
    observer.start()

    try:
        while True:
            git_pull_changes()
            time.sleep(30)  # Pull every 30 seconds
    except KeyboardInterrupt:
        observer.stop()

    observer.join()
