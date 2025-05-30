import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from bookmarks_import import import_bookmarks  # <-- You must define this function


class ImportChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith("Bookmarks_Chrome.json"):
            print("📥 Synced bookmarks changed, importing...")
            import_bookmarks(event.src_path)


if __name__ == "__main__":
    bookmarks_file = Path.cwd() / "exported_bookmarks" / "Bookmarks_Chrome.json"
    event_handler = ImportChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, path=str(bookmarks_file.parent), recursive=False)

    print(f"👀 Watching for synced file changes in: {bookmarks_file.parent}")
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()
