# monitor_bookmarks.py
import time, subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from bookmarks_export import export_bookmarks, get_chrome_bookmarks_path
from checksum_utils import calc_checksum, read_last, write_last

STATE_FILE = Path.cwd() / "state" / "last_import_checksum.txt"
EXPORT_DIR = Path.cwd() / "exported_bookmarks"


class BookmarkChangeHandler(FileSystemEventHandler):
    def __init__(self):
        self.chrome_file = get_chrome_bookmarks_path()
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    def on_modified(self, event):
        if event.is_directory or not event.src_path.endswith("Bookmarks"):
            return

        current = calc_checksum(self.chrome_file)
        last_import = read_last(STATE_FILE)
        if current == last_import:
            print("🔒 No new content since last import → skipping export")
            return

        print("📌 Genuine bookmark change → exporting…")
        export_bookmarks(EXPORT_DIR)

        subprocess.run(["git", "add", "."], check=False)
        subprocess.run(["git", "commit", "-m", "🔁 Auto‑sync export"], check=False)
        subprocess.run(["git", "push"], check=False)
        print("🚀 Export pushed to GitHub")

        write_last(STATE_FILE, current)


if __name__ == "__main__":
    handler = BookmarkChangeHandler()
    observer = Observer()
    observer.schedule(handler, str(handler.chrome_file.parent), recursive=False)
    print(f"👀 Watching Chrome bookmarks in {handler.chrome_file.parent}")
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
