import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from bookmarks_export import export_bookmarks, get_chrome_bookmarks_path


class BookmarkChangeHandler(FileSystemEventHandler):
    def __init__(self, export_dir):
        self.export_dir = Path(export_dir)

    def on_modified(self, event):
        if event.src_path.endswith("Bookmarks"):
            print("📌 Bookmarks changed, exporting...")
            export_bookmarks(self.export_dir)


if __name__ == "__main__":
    bookmarks_path = get_chrome_bookmarks_path()
    folder_to_watch = bookmarks_path.parent
    export_dir = Path.cwd() / "exported_bookmarks"

    event_handler = BookmarkChangeHandler(export_dir)
    observer = Observer()
    observer.schedule(event_handler, path=str(folder_to_watch), recursive=False)

    print(f"👀 Watching for changes in: {folder_to_watch}")
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()
