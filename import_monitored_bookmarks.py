import time
import subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from bookmarks_import import import_bookmarks

SUPPRESS_AFTER_EXPORT = 5
last_export_time = 0


def git_pull_and_import(json_path):
    global last_export_time
    subprocess.run(["git", "pull"], check=False)
    print("⬇️ Pulled from GitHub")
    # wait for Chrome to close (if on Windows)
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
    last_export_time = time.time()


class ImportChangeHandler(FileSystemEventHandler):
    def __init__(self, json_path):
        self.json_path = Path(json_path)

    def on_modified(self, event):
        global last_export_time
        now = time.time()
        # skip if we just exported
        if now - last_export_time < SUPPRESS_AFTER_EXPORT:
            return

        if event.src_path.endswith(self.json_path.name):
            print("📥 Detected synced JSON change, pulling & importing…")
            git_pull_and_import(self.json_path)


if __name__ == "__main__":
    json_file = Path.cwd() / "exported_bookmarks" / "Bookmarks_Chrome.json"
    handler = ImportChangeHandler(json_file)
    obs = Observer()
    obs.schedule(handler, str(json_file.parent), recursive=False)

    print(f"👀 Watching synced JSON in: {json_file.parent}")
    obs.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        obs.stop()
    obs.join()
