import time, subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from bookmarks_export import export_bookmarks, get_chrome_bookmarks_path
from checksum_utils import calc_checksum, read_last, write_last

# Where we store the last checksum of Chrome's Bookmarks after import,
# so we can skip mirrored writes.
STATE_FILE = Path.cwd() / "state" / "last_import_checksum.txt"
EXPORT_DIR = Path.cwd() / "exported_bookmarks"


class BookmarkChangeHandler(FileSystemEventHandler):
    def __init__(self):
        self.chrome_file = get_chrome_bookmarks_path()
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    def on_modified(self, event):
        if event.is_directory:
            return
        if not event.src_path.endswith("Bookmarks"):
            return

        # 1) Compute checksum of Chrome's live Bookmarks file
        current = calc_checksum(self.chrome_file)
        # 2) Load the checksum we recorded after last import
        last_import = read_last(STATE_FILE)
        if current == last_import:
            print("🔒 Change matches last import → skipping export")
            return

        # 3) It's a genuine user edit → export and push
        print("📌 Bookmarks changed, exporting…")
        export_bookmarks(EXPORT_DIR)

        subprocess.run(["git", "add", "."], check=False)
        subprocess.run(["git", "commit", "-m", "🔁 Auto‑sync export"], check=False)
        subprocess.run(["git", "push"], check=False)
        print("🚀 Export pushed to GitHub")

        # 4) Update the state file so future mirrored writes are skipped
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
