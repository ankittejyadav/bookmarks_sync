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
        self.last_hash = None
        self.import_lock = threading.Lock()
        self.last_import_time = 0
        self.cooldown_period = 5  # 5 seconds cooldown
        self.processing = False

    def get_file_hash(self, filepath):
        """Get file hash to detect actual changes"""
        try:
            with open(filepath, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return None

    def on_modified(self, event):
        if event.is_directory or self.processing:
            return
            
        if event.src_path.endswith("Bookmarks_Chrome.json"):
            current_time = time.time()
            
            # Check cooldown period
            if current_time - self.last_import_time < self.cooldown_period:
                print("⏳ Import cooldown active, skipping")
                return
            
            # Check if file actually changed
            current_hash = self.get_file_hash(event.src_path)
            if current_hash and current_hash == self.last_hash:
                print("📄 File unchanged, skipping import")
                return
            
            with self.import_lock:
                if not self.processing:
                    self.processing = True
                    print("📥 Synced bookmarks changed, importing...")
                    
                    # Wait for file to be fully written
                    time.sleep(2)
                    
                    try:
                        import_bookmarks(event.src_path)
                        self.last_hash = current_hash
                        self.last_import_time = current_time
                    except Exception as e:
                        print(f"❌ Import failed: {e}")
                    finally:
                        self.processing = False


def git_pull_changes():
    try:
        # Check if there are remote changes first
        subprocess.run(["git", "fetch"], check=True, capture_output=True)
        
        # Check if local is behind remote
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD..origin/main"], 
            capture_output=True, text=True, check=True
        )
        
        if result.stdout.strip() != "0":
            subprocess.run(["git", "pull"], check=True)
            print("📥 Pulled latest from GitHub")
            return True
        else:
            print("✅ Already up to date")
            return False
    except subprocess.CalledProcessError as e:
        print(f"❌ Git pull failed: {e}")
        return False


def is_chrome_running():
    """Check if Chrome is running"""
    try:
        import psutil
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] and 'chrome.exe' in proc.info['name'].lower():
                return True
        return False
    except ImportError:
        print("⚠️ psutil not installed, cannot check Chrome status")
        return False


if __name__ == "__main__":
    bookmarks_file = Path.cwd() / "exported_bookmarks" / "Bookmarks_Chrome.json"
    bookmarks_dir = bookmarks_file.parent

    # Ensure directory exists
    bookmarks_dir.mkdir(exist_ok=True)
    
    # Check Chrome status
    if is_chrome_running():
        print("⚠️ Chrome is running. Close Chrome for reliable sync or expect occasional permission errors.")

    event_handler = ImportChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, path=str(bookmarks_dir), recursive=False)

    print(f"👀 Watching for synced file changes in: {bookmarks_dir}")
    print("🔄 Will check for remote updates every 30 seconds")
    print("🛑 Press Ctrl+C to stop")
    
    observer.start()

    try:
        while True:
            if git_pull_changes():
                # If we pulled changes, the file watcher will handle the import
                time.sleep(5)  # Give file watcher time to process
            time.sleep(30)  # Check every 30 seconds
    except KeyboardInterrupt:
        print("\n🛑 Stopping import monitor...")
        observer.stop()

    observer.join()
    print("✅ Import monitor stopped")