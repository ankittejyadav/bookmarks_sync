import time
import subprocess
import threading
import hashlib
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from bookmarks_export import export_bookmarks, get_chrome_bookmarks_path


class BookmarkChangeHandler(FileSystemEventHandler):
    def __init__(self, export_dir):
        self.export_dir = Path(export_dir)
        self.last_hash = None
        self.last_export_time = 0
        self.cooldown_period = 5  # 5 seconds cooldown
        self.processing_lock = threading.Lock()
        self.ignore_next_change = False
        
        # Initialize with current file hash
        self._update_current_hash()

    def _get_file_hash(self, file_path):
        """Get MD5 hash of file to detect actual changes"""
        try:
            if not Path(file_path).exists():
                return None
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except (PermissionError, OSError):
            return None

    def _update_current_hash(self):
        """Update the current hash of bookmarks file"""
        bookmarks_path = get_chrome_bookmarks_path()
        self.last_hash = self._get_file_hash(bookmarks_path)

    def on_any_event(self, event):
        if event.is_directory:
            return

        # Only process Bookmarks file changes
        if not any(event.src_path.endswith(name) for name in ["Bookmarks", "Bookmarks.bak"]):
            return

        # Skip if we're ignoring changes (during our own import)
        if self.ignore_next_change:
            print("🔇 Ignoring self-triggered change")
            return

        current_time = time.time()
        
        # Cooldown check
        if current_time - self.last_export_time < self.cooldown_period:
            print(f"⏰ Cooldown active, skipping export")
            return

        # Use lock to prevent concurrent processing
        if not self.processing_lock.acquire(blocking=False):
            print("🔒 Already processing, skipping")
            return

        try:
            # Check if file actually changed by comparing hash
            current_hash = self._get_file_hash(event.src_path)
            if current_hash and current_hash == self.last_hash:
                print("📄 File hash unchanged, skipping export")
                return

            print("📌 Real bookmark change detected, exporting...")
            
            # Wait for file to be stable (Chrome might still be writing)
            time.sleep(1)
            
            # Export and push
            if self._safe_export():
                self.last_hash = current_hash
                self.last_export_time = current_time
                
        finally:
            self.processing_lock.release()

    def _safe_export(self):
        """Safely export bookmarks with error handling"""
        try:
            export_bookmarks(self.export_dir)
            git_push_changes()
            return True
        except Exception as e:
            print(f"❌ Export failed: {e}")
            return False

    def set_ignore_next_change(self, ignore=True):
        """Set flag to ignore next change (used during import)"""
        self.ignore_next_change = ignore
        if ignore:
            # Auto-reset after a short delay
            threading.Timer(3.0, lambda: setattr(self, 'ignore_next_change', False)).start()


def git_push_changes():
    try:
        # Check if there are actually changes to commit
        result = subprocess.run(["git", "status", "--porcelain"], 
                              capture_output=True, text=True, check=True)
        
        if not result.stdout.strip():
            print("📝 No changes to commit")
            return
            
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", "🔁 Auto-sync bookmark changes"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("🚀 Pushed to GitHub")
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Git operation failed: {e}")


# Global handler instance for communication with import script
handler_instance = None


if __name__ == "__main__":
    bookmarks_path = get_chrome_bookmarks_path()
    folder_to_watch = bookmarks_path.parent
    export_dir = Path.cwd() / "exported_bookmarks"

    handler_instance = BookmarkChangeHandler(export_dir)
    event_handler = handler_instance
    observer = Observer()
    observer.schedule(event_handler, path=str(folder_to_watch), recursive=False)

    print(f"👀 Watching for changes in: {folder_to_watch}")
    print(f"💾 Exporting to: {export_dir}")
    print("⚡ Infinite loop protection: ACTIVE")
    
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping monitor...")
        observer.stop()

    observer.join()
