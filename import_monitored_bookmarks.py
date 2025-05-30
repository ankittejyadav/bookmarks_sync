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
from bookmarks_import import import_bookmarks

# Debounce class as above…


def git_pull_and_import(json_path):
    print("🔄 Debounced pull/import triggered")
    subprocess.run(["git", "pull"], check=False)
    print("⬇️ Pulled latest from GitHub")
    # wait until Chrome is closed (from earlier solution)
    while (
        subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq chrome.exe"],
            capture_output=True,
            text=True,
        ).stdout.find("chrome.exe")
        != -1
    ):
        print("⏳ Chrome open, delaying import…")
        time.sleep(5)
    import_bookmarks(json_path)


class ImportChangeHandler(FileSystemEventHandler):
    def __init__(self, json_path):
        self.json_path = Path(json_path)
        self.debouncer = Debouncer(2.0, lambda: git_pull_and_import(self.json_path))

    def on_modified(self, event):
        if event.src_path.endswith(self.json_path.name):
            self.debouncer.trigger()


if __name__ == "__main__":
    json_file = Path.cwd() / "exported_bookmarks" / "Bookmarks_Chrome.json"
    handler = ImportChangeHandler(json_file)
    obs = Observer()
    obs.schedule(handler, str(json_file.parent), recursive=False)

    print(f"👀 Watching for synced file in: {json_file.parent}")
    obs.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        obs.stop()
    obs.join()
