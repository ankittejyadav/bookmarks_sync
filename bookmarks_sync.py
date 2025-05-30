import time
import subprocess
from pathlib import Path
from threading import Event, Thread
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from bookmarks_export import export_bookmarks, get_chrome_bookmarks_path
from bookmarks_import import import_bookmarks

BOOKMARKS_JSON = Path.cwd() / "exported_bookmarks" / "Bookmarks_Chrome.json"
BOOKMARKS_DIR = BOOKMARKS_JSON.parent
CHROME_BOOKMARKS = get_chrome_bookmarks_path()
CHROME_DIR = CHROME_BOOKMARKS.parent

# Prevent recursion
suppress_export = Event()
suppress_import = Event()


def git_commit_and_push():
    try:
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", "🔁 Auto-sync new bookmark"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("🚀 Pushed to GitHub")
    except subprocess.CalledProcessError as e:
        print(f"❌ Git push failed: {e}")


def git_pull():
    try:
        subprocess.run(["git", "pull", "--rebase"], check=True)
        print("📥 Pulled latest from GitHub")
    except subprocess.CalledProcessError as e:
        print(f"❌ Git pull failed: {e}")


class SyncHandler(FileSystemEventHandler):
    def on_modified(self, event):
        path = Path(event.src_path)
        if path.name in ["Bookmarks", "Bookmarks-journal"]:
            if not suppress_export.is_set():
                print("📌 Detected Chrome bookmark change, exporting…")
                suppress_import.set()
                export_bookmarks(BOOKMARKS_DIR)
                git_commit_and_push()
                time.sleep(1)
                suppress_import.clear()
        elif path.name == BOOKMARKS_JSON.name:
            if not suppress_import.is_set():
                print("📥 Detected synced file change, importing…")
                suppress_export.set()
                git_pull()
                import_bookmarks(str(BOOKMARKS_JSON))
                time.sleep(1)
                suppress_export.clear()


def periodic_git_pull():
    while True:
        if not suppress_import.is_set():
            suppress_import.set()
            git_pull()
            suppress_import.clear()
        time.sleep(30)


if __name__ == "__main__":
    print(f"👀 Watching Chrome: {CHROME_DIR}")
    print(f"👀 Watching Synced JSON: {BOOKMARKS_DIR}")

    handler = SyncHandler()
    observer = Observer()
    observer.schedule(handler, path=str(CHROME_DIR), recursive=False)
    observer.schedule(handler, path=str(BOOKMARKS_DIR), recursive=False)
    observer.start()

    # Background thread for periodic pull
    Thread(target=periodic_git_pull, daemon=True).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
