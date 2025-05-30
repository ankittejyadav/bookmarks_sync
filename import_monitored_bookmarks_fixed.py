import time
import subprocess
import threading
import hashlib
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from bookmarks_import import import_bookmarks


class ImportChangeHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_import_time = 0
        self.cooldown_period = 5  # 5 seconds cooldown
        self.processing_lock = threading.Lock()
        self.last_hash = None
        
        # Initialize current hash
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
        """Update hash of the synced bookmarks file"""
        bookmarks_file = Path.cwd() / "exported_bookmarks" / "Bookmarks_Chrome.json"
        self.last_hash = self._get_file_hash(bookmarks_file)

    def on_modified(self, event):
        if not event.src_path.endswith("Bookmarks_Chrome.json"):
            return

        current_time = time.time()
        
        # Cooldown check
        if current_time - self.last_import_time < self.cooldown_period:
            print("⏰ Import cooldown active, skipping")
            return

        # Lock to prevent concurrent imports
        if not self.processing_lock.acquire(blocking=False):
            print("🔒 Import already in progress, skipping")
            return

        try:
            # Check if file actually changed
            current_hash = self._get_file_hash(event.src_path)
            if current_hash and current_hash == self.last_hash:
                print("📄 Synced file hash unchanged, skipping import")
                return

            print("📥 New synced bookmarks detected, importing...")
            
            # Wait for file to be stable
            time.sleep(1)
            
            # Notify monitor to ignore next change (prevent loop)
            self._notify_monitor_to_ignore()
            
            # Perform import
            if self._safe_import(event.src_path):
                self.last_hash = current_hash
                self.last_import_time = current_time
                
        finally:
            self.processing_lock.release()

    def _safe_import(self, import_file):
        """Safely import bookmarks with error handling"""
        try:
            import_bookmarks(import_file)
            print("✅ Import completed successfully")
            return True
        except Exception as e:
            print(f"❌ Import failed: {e}")
            return False

    def _notify_monitor_to_ignore(self):
        """Tell the monitor script to ignore the next change"""
        try:
            # Try to communicate with monitor script if running
            # This is a simple approach - in production, use proper IPC
            import monitor_bookmarks_fixed
            if hasattr(monitor_bookmarks_fixed, 'handler_instance') and monitor_bookmarks_fixed.handler_instance:
                monitor_bookmarks_fixed.handler_instance.set_ignore_next_change(True)
                print("🔇 Notified monitor to ignore next change")
        except (ImportError, AttributeError):
            print("⚠️ Could not notify monitor script (running separately?)")


def git_pull_changes():
    """Pull latest changes from git repository"""
    try:
        result = subprocess.run(["git", "pull"], capture_output=True, text=True, check=True)
        
        # Only print if there were actual changes
        if "Already up to date" not in result.stdout:
            print("📥 Pulled latest changes from GitHub")
            return True
        return False
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Git pull failed: {e}")
        return False


if __name__ == "__main__":
    bookmarks_file = Path.cwd() / "exported_bookmarks" / "Bookmarks_Chrome.json"
    bookmarks_dir = bookmarks_file.parent

    # Create export directory if it doesn't exist
    bookmarks_dir.mkdir(parents=True, exist_ok=True)

    event_handler = ImportChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, path=str(bookmarks_dir), recursive=False)

    print(f"👀 Watching for synced file changes in: {bookmarks_dir}")
    print("⚡ Infinite loop protection: ACTIVE")
    
    observer.start()

    try:
        pull_counter = 0
        while True:
            # Pull every 30 seconds, but don't spam the output
            if pull_counter % 30 == 0:  # Every 30 seconds
                git_pull_changes()
            
            time.sleep(1)
            pull_counter += 1
            
    except KeyboardInterrupt:
        print("\n🛑 Stopping import monitor...")
        observer.stop()

    observer.join()
