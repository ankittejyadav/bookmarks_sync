# import_monitored_bookmarks.py
import time, subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from bookmarks_import import import_bookmarks, get_chrome_bookmarks_path
from checksum_utils import calc_checksum, read_last, write_last

JSON_FILE = Path.cwd() / "exported_bookmarks" / "Bookmarks_Chrome.json"
STATE_FILE = Path.cwd() / "state" / "last_export_checksum.txt"


class ImportChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.is_directory or not event.src_path.endswith(JSON_FILE.name):
            return

        current = calc_checksum(JSON_FILE)
        last_export = read_last(STATE_FILE)
        if current == last_export:
            print("🔒 JSON matches last export → skipping import")
            return

        print("📥 New JSON detected → pulling & importing…")
        subprocess.run(["git", "pull"], check=False)
        import_bookmarks(str(JSON_FILE))

        chrome_file = get_chrome_bookmarks_path()
        new_sum = calc_checksum(chrome_file)
        write_last(STATE_FILE, new_sum)
        print("✅ Import complete; state updated")


if __name__ == "__main__":
    JSON_FILE.parent.mkdir(parents=True, exist_ok=True)
    handler = ImportChangeHandler()
    observer = Observer()
    observer.schedule(handler, str(JSON_FILE.parent), recursive=False)
    print(f"👀 Watching synced JSON in {JSON_FILE.parent}")
    observer.start()
    try:
        while True:
            time.sleep(30)
            # periodic pull in case we miss a filesystem event
            subprocess.run(["git", "pull"], check=False)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
