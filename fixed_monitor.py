import time
import subprocess
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from bookmarks_export import export_bookmarks, get_chrome_bookmarks_path


class BookmarkChangeHandler(FileSystemEventHandler):
    def __init__(self, export_dir):
        self.export_dir = Path(export_dir)
        self.last_export_time = 0
        self.export_lock = threading.Lock()
        self.cooldown_period = 5  # 5 seconds cooldown
        self.processing = False

    def on_any_event(self, event):
        if event.is_directory or self.processing:
            return

        if any(
            event.src_path.endswith(name) for name in ["Bookmarks", "Bookmarks-journal"]
        ):
            current_time = time.time()

            # Check cooldown period
            if current_time - self.last_export_time < self.cooldown_period:
                print("⏳ Cooldown period active, skipping export")
                return

            with self.export_lock:
                if not self.processing:
                    self.processing = True
                    print("📌 Bookmarks file event detected, exporting...")

                    # Wait for file to stabilize
                    time.sleep(1)

                    try:
                        export_bookmarks(self.export_dir)
                        git_push_changes()
                        self.last_export_time = current_time
                    except Exception as e:
                        print(f"❌ Export failed: {e}")
                    finally:
                        self.processing = False


def git_push_changes():
    try:
        # Check if there are actually changes to commit
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"], capture_output=True
        )
        if result.returncode != 0:  # There are changes
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(
                ["git", "commit", "-m", "🔁 Auto-sync new bookmark"], check=True
            )
            subprocess.run(["git", "push"], check=True)
            print("🚀 Pushed to GitHub")
        else:
            print("ℹ️ No changes to push")
    except subprocess.CalledProcessError as e:
        print(f"❌ Git push failed: {e}")


def is_chrome_running():
    """Check if Chrome is running to avoid permission issues"""
    try:
        import psutil

        for proc in psutil.process_iter(["name"]):
            if proc.info["name"] and "chrome.exe" in proc.info["name"].lower():
                return True
        return False
    except ImportError:
        print("⚠️ psutil not installed, cannot check Chrome status")
        return False


if __name__ == "__main__":
    bookmarks_path = get_chrome_bookmarks_path()
    folder_to_watch = bookmarks_path.parent
    export_dir = Path.cwd() / "exported_bookmarks"

    # Check Chrome status
    if is_chrome_running():
        print(
            "⚠️ Chrome is running. Close Chrome for reliable sync or expect occasional permission errors."
        )

    event_handler = BookmarkChangeHandler(export_dir)
    observer = Observer()
    observer.schedule(event_handler, path=str(folder_to_watch), recursive=False)

    print(f"👀 Watching for changes in: {folder_to_watch}")
    print(f"📁 Export directory: {export_dir}")
    print("🛑 Press Ctrl+C to stop")

    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping monitor...")
        observer.stop()

    observer.join()
    print("✅ Monitor stopped")
