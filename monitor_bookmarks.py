import threading


class Debouncer:
    def __init__(self, delay, action):
        self.delay = delay
        self.action = action
        self.timer = None
        self.lock = threading.Lock()

    def trigger(self, *args, **kwargs):
        with self.lock:
            if self.timer:
                self.timer.cancel()
            self.timer = threading.Timer(
                self.delay, self._run, args=args, kwargs=kwargs
            )
            self.timer.daemon = True
            self.timer.start()

    def _run(self, *args, **kwargs):
        with self.lock:
            self.timer = None
        self.action(*args, **kwargs)


import time
import subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from bookmarks_export import export_bookmarks, get_chrome_bookmarks_path

# Debounce class as above…


def git_push_changes():
    subprocess.run(["git", "add", "."], check=False)
    subprocess.run(["git", "commit", "-m", "🔁 Auto-sync new bookmark"], check=False)
    subprocess.run(["git", "push"], check=False)
    print("🚀 Pushed to GitHub")


def do_export(export_dir):
    print("📌 Debounced export triggered")
    export_bookmarks(export_dir)
    git_push_changes()


class BookmarkChangeHandler(FileSystemEventHandler):
    def __init__(self, export_dir):
        self.export_dir = Path(export_dir)
        # 2s debounce
        self.debouncer = Debouncer(2.0, lambda: do_export(self.export_dir))

    def on_modified(self, event):
        # only react to Chrome's Bookmarks file
        if event.src_path.endswith("Bookmarks"):
            self.debouncer.trigger()


if __name__ == "__main__":
    bookmarks_path = get_chrome_bookmarks_path()
    folder_to_watch = bookmarks_path.parent
    export_dir = Path.cwd() / "exported_bookmarks"

    handler = BookmarkChangeHandler(export_dir)
    obs = Observer()
    obs.schedule(handler, str(folder_to_watch), recursive=False)

    print(f"👀 Watching for changes in: {folder_to_watch}")
    obs.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        obs.stop()
    obs.join()
