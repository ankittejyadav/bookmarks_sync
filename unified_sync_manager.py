import time
import subprocess
import threading
import hashlib
import os
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from bookmarks_export import export_bookmarks, get_chrome_bookmarks_path
from bookmarks_import import import_bookmarks


class UnifiedBookmarkSyncManager:
    def __init__(self, export_dir):
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        
        # Prevent infinite loops
        self.sync_lock = threading.Lock()
        self.last_chrome_bookmarks_hash = None
        self.last_export_bookmarks_hash = None
        self.last_sync_time = 0
        self.cooldown_period = 10  # 10 seconds between syncs
        self.syncing = False
        
        # File paths
        self.chrome_bookmarks = get_chrome_bookmarks_path()
        self.export_file = self.export_dir / "Bookmarks_Chrome.json"

    def get_file_hash(self, filepath):
        """Get MD5 hash of file content"""
        try:
            if not Path(filepath).exists():
                return None
            with open(filepath, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            print(f"❌ Error reading {filepath}: {e}")
            return None

    def get_bookmarks_content_hash(self, filepath):
        """Get hash of only bookmark structure, ignoring metadata"""
        try:
            if not Path(filepath).exists():
                return None
                
            import json
            with open(filepath, 'r', encoding='utf-8') as f:
                bookmarks_data = json.load(f)
            
            # Extract only bookmark structure, ignore metadata
            bookmark_content = self.extract_bookmark_structure(bookmarks_data)
            bookmark_json = json.dumps(bookmark_content, sort_keys=True)
            return hashlib.md5(bookmark_json.encode()).hexdigest()
            
        except Exception as e:
            print(f"❌ Error reading bookmark content from {filepath}: {e}")
            return None

    def extract_bookmark_structure(self, data):
        """Extract only bookmark folders and URLs, ignore metadata"""
        def clean_node(node):
            if isinstance(node, dict):
                cleaned = {}
                
                # Keep essential bookmark data only
                if 'type' in node:
                    cleaned['type'] = node['type']
                
                if 'name' in node:
                    cleaned['name'] = node['name']
                
                if 'url' in node:
                    cleaned['url'] = node['url']
                
                # Recursively clean children
                if 'children' in node and isinstance(node['children'], list):
                    cleaned['children'] = [clean_node(child) for child in node['children']]
                
                return cleaned
            return node
        
        # Extract bookmark roots only
        cleaned_data = {}
        if 'roots' in data:
            cleaned_data['roots'] = {}
            for root_name, root_data in data['roots'].items():
                if isinstance(root_data, dict):
                    cleaned_data['roots'][root_name] = clean_node(root_data)
        
        return cleaned_data

    def is_chrome_running(self):
        """Check if Chrome is running"""
        try:
            import psutil
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] and 'chrome.exe' in proc.info['name'].lower():
                    return True
            return False
        except ImportError:
            return False

    def wait_for_file_access(self, filepath, max_wait=5):
        """Wait for file to be accessible"""
        for _ in range(max_wait * 10):
            try:
                if os.path.exists(filepath) and os.access(filepath, os.R_OK):
                    return True
                time.sleep(0.1)
            except:
                time.sleep(0.1)
        return False

    def sync_from_chrome(self):
        """Export from Chrome and push to Git"""
        if self.syncing:
            return
            
        current_time = time.time()
        if current_time - self.last_sync_time < self.cooldown_period:
            print("⏳ Sync cooldown active")
            return

        with self.sync_lock:
            if self.syncing:
                return
                
            self.syncing = True
            print("📤 Syncing FROM Chrome...")
            
            try:
                # Wait for Chrome bookmarks to be stable
                if not self.wait_for_file_access(self.chrome_bookmarks):
                    print("❌ Cannot access Chrome bookmarks")
                    return
                
                # Check if Chrome bookmarks actually changed (content-wise)
                current_chrome_hash = self.get_bookmarks_content_hash(self.chrome_bookmarks)
                if current_chrome_hash == self.last_chrome_bookmarks_hash:
                    print("📄 Chrome bookmarks content unchanged (metadata only)")
                    return
                
                print("🔍 Detected actual bookmark changes (not just metadata)")
                
                # Export bookmarks
                export_bookmarks(self.export_dir)
                
                # Update hash
                self.last_chrome_bookmarks_hash = current_chrome_hash
                self.last_export_bookmarks_hash = self.get_bookmarks_content_hash(self.export_file)
                
                # Push to Git
                self.git_push()
                
                self.last_sync_time = current_time
                print("✅ Chrome → Git sync complete")
                
            except Exception as e:
                print(f"❌ Chrome sync failed: {e}")
            finally:
                self.syncing = False

    def sync_to_chrome(self):
        """Import to Chrome from Git"""
        if self.syncing:
            return
            
        current_time = time.time()
        if current_time - self.last_sync_time < self.cooldown_period:
            return

        with self.sync_lock:
            if self.syncing:
                return
                
            self.syncing = True
            print("📥 Syncing TO Chrome...")
            
            try:
                # Check if export file changed (content-wise)
                current_export_hash = self.get_bookmarks_content_hash(self.export_file)
                if current_export_hash == self.last_export_bookmarks_hash:
                    print("📄 Export file bookmarks unchanged")
                    return
                
                print("🔍 Detected bookmark changes in export file")
                
                # Import to Chrome
                import_bookmarks(self.export_file)
                
                # Update hashes
                self.last_export_bookmarks_hash = current_export_hash
                self.last_chrome_bookmarks_hash = self.get_bookmarks_content_hash(self.chrome_bookmarks)
                
                self.last_sync_time = current_time
                print("✅ Git → Chrome sync complete")
                
            except Exception as e:
                print(f"❌ Chrome import failed: {e}")
            finally:
                self.syncing = False

    def git_push(self):
        """Push changes to Git"""
        try:
            # Check if there are changes
            result = subprocess.run(
                ["git", "diff", "--quiet"], 
                capture_output=True, cwd=self.export_dir.parent
            )
            
            if result.returncode != 0:  # There are changes
                subprocess.run(["git", "add", "."], check=True, cwd=self.export_dir.parent)
                subprocess.run(
                    ["git", "commit", "-m", "🔁 Auto-sync bookmarks"], 
                    check=True, cwd=self.export_dir.parent
                )
                subprocess.run(["git", "push"], check=True, cwd=self.export_dir.parent)
                print("🚀 Pushed to Git")
            else:
                print("ℹ️ No changes to push")
                
        except subprocess.CalledProcessError as e:
            print(f"❌ Git push failed: {e}")

    def git_pull(self):
        """Pull changes from Git"""
        try:
            # Fetch first
            subprocess.run(["git", "fetch"], check=True, capture_output=True, 
                         cwd=self.export_dir.parent)
            
            # Check if behind
            result = subprocess.run(
                ["git", "rev-list", "--count", "HEAD..origin/main"],
                capture_output=True, text=True, check=True,
                cwd=self.export_dir.parent
            )
            
            if result.stdout.strip() != "0":
                subprocess.run(["git", "pull"], check=True, cwd=self.export_dir.parent)
                print("📥 Pulled from Git")
                return True
            return False
                
        except subprocess.CalledProcessError as e:
            print(f"❌ Git pull failed: {e}")
            return False


class ChromeBookmarkHandler(FileSystemEventHandler):
    def __init__(self, sync_manager):
        self.sync_manager = sync_manager

    def on_any_event(self, event):
        if event.is_directory:
            return
            
        if any(event.src_path.endswith(name) for name in ["Bookmarks", "Bookmarks-journal"]):
            print("📌 Chrome bookmarks changed")
            # Small delay to let Chrome finish writing
            time.sleep(1)
            self.sync_manager.sync_from_chrome()


class ExportFileHandler(FileSystemEventHandler):
    def __init__(self, sync_manager):
        self.sync_manager = sync_manager

    def on_modified(self, event):
        if event.src_path.endswith("Bookmarks_Chrome.json"):
            print("📥 Export file changed")
            # Small delay to let file write complete
            time.sleep(1)
            self.sync_manager.sync_to_chrome()


def main():
    export_dir = Path.cwd() / "exported_bookmarks"
    sync_manager = UnifiedBookmarkSyncManager(export_dir)
    
    # Check Chrome status
    if sync_manager.is_chrome_running():
        print("⚠️ Chrome is running. For best results, close Chrome during sync setup.")
        print("   Continuing anyway, but expect occasional permission errors...")
        time.sleep(3)
    
    # Set up watchers
    chrome_handler = ChromeBookmarkHandler(sync_manager)
    export_handler = ExportFileHandler(sync_manager)
    
    observer = Observer()
    
    # Watch Chrome bookmarks directory
    chrome_dir = sync_manager.chrome_bookmarks.parent
    observer.schedule(chrome_handler, path=str(chrome_dir), recursive=False)
    
    # Watch export directory
    observer.schedule(export_handler, path=str(export_dir), recursive=False)
    
    print("🔄 Unified Bookmark Sync Manager Started")
    print(f"👀 Watching Chrome: {chrome_dir}")
    print(f"👀 Watching Export: {export_dir}")
    print("🔄 Will check Git every 60 seconds")
    print("🛑 Press Ctrl+C to stop")
    
    observer.start()
    
    try:
        while True:
            # Periodic Git pull check
            if sync_manager.git_pull():
                # If we pulled changes, sync to Chrome
                time.sleep(2)  # Let file system settle
                sync_manager.sync_to_chrome()
            
            time.sleep(60)  # Check every minute
            
    except KeyboardInterrupt:
        print("\n🛑 Stopping sync manager...")
        observer.stop()
    
    observer.join()
    print("✅ Sync manager stopped")


if __name__ == "__main__":
    main()