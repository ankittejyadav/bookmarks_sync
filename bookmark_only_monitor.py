import time
import subprocess
import threading
import hashlib
import json
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from bookmarks_export import export_bookmarks, get_chrome_bookmarks_path


class BookmarkOnlyHandler(FileSystemEventHandler):
    def __init__(self, export_dir):
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        
        self.sync_lock = threading.Lock()
        self.last_bookmark_hash = None
        self.last_sync_time = 0
        self.cooldown_period = 5  # 5 seconds between syncs
        self.processing = False
        
        # Initialize with current bookmark state
        chrome_bookmarks = get_chrome_bookmarks_path()
        self.last_bookmark_hash = self.get_bookmark_structure_hash(chrome_bookmarks)
        print(f"📊 Initial bookmark hash: {self.last_bookmark_hash[:8]}...")

    def get_bookmark_structure_hash(self, filepath):
        """Get hash of only bookmark structure (URLs, names, folders)"""
        try:
            if not Path(filepath).exists():
                return None
                
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract only bookmark structure
            bookmark_structure = self.extract_bookmark_urls_and_names(data)
            structure_json = json.dumps(bookmark_structure, sort_keys=True)
            
            return hashlib.md5(structure_json.encode()).hexdigest()
            
        except Exception as e:
            print(f"❌ Error reading bookmark structure: {e}")
            return None

    def extract_bookmark_urls_and_names(self, data):
        """Extract only URLs, names, and folder structure"""
        def extract_from_node(node):
            if not isinstance(node, dict):
                return None
                
            result = {}
            
            # Only include bookmark type and name
            if 'type' in node:
                result['type'] = node['type']
            
            if 'name' in node:
                result['name'] = node['name']
            
            # Include URL only for actual bookmarks (not folders)
            if 'url' in node and node.get('type') == 'url':
                result['url'] = node['url']
            
            # Process children recursively
            if 'children' in node and isinstance(node['children'], list):
                children = []
                for child in node['children']:
                    child_result = extract_from_node(child)
                    if child_result:
                        children.append(child_result)
                if children:
                    result['children'] = children
            
            return result
        
        # Extract from bookmark roots only
        if 'roots' not in data:
            return {}
            
        extracted = {'roots': {}}
        for root_name, root_data in data['roots'].items():
            # Focus on bookmark_bar, other, and synced bookmarks
            if root_name in ['bookmark_bar', 'other', 'synced']:
                extracted_root = extract_from_node(root_data)
                if extracted_root:
                    extracted['roots'][root_name] = extracted_root
        
        return extracted

    def on_any_event(self, event):
        if event.is_directory or self.processing:
            return

        # Only process bookmark file changes
        if not any(event.src_path.endswith(name) for name in ["Bookmarks"]):
            return
            
        # Skip journal files - they're just Chrome's internal logging
        if event.src_path.endswith("Bookmarks-journal"):
            return
            
        current_time = time.time()
        
        # Cooldown check
        if current_time - self.last_sync_time < self.cooldown_period:
            return
        
        with self.sync_lock:
            if self.processing:
                return
                
            self.processing = True
            
            try:
                # Wait for file to stabilize
                time.sleep(2)
                
                print("🔍 Checking for actual bookmark changes...")
                
                # Get current bookmark structure
                current_hash = self.get_bookmark_structure_hash(event.src_path)
                
                if current_hash is None:
                    print("❌ Could not read bookmark file")
                    return
                
                # Compare with last known state
                if current_hash == self.last_bookmark_hash:
                    print("📄 No bookmark changes detected (only metadata/navigation)")
                    return
                
                print("🔥 ACTUAL BOOKMARK CHANGES DETECTED!")
                print(f"   Old hash: {self.last_bookmark_hash[:8] if self.last_bookmark_hash else 'None'}...")
                print(f"   New hash: {current_hash[:8]}...")
                
                # Export and sync
                export_bookmarks(self.export_dir)
                self.git_push_changes()
                
                # Update state
                self.last_bookmark_hash = current_hash
                self.last_sync_time = current_time
                
                print("✅ Bookmark sync completed")
                
            except Exception as e:
                print(f"❌ Sync error: {e}")
            finally:
                self.processing = False

    def git_push_changes(self):
        """Push changes to git"""
        try:
            # Check if there are actually changes to commit
            result = subprocess.run(["git", "status", "--porcelain"], 
                                  capture_output=True, text=True)
            
            if result.stdout.strip():  # There are changes
                subprocess.run(["git", "add", "."], check=True)
                subprocess.run(["git", "commit", "-m", "🔖 Bookmark changes detected"], check=True)
                subprocess.run(["git", "push"], check=True)
                print("🚀 Pushed bookmark changes to Git")
            else:
                print("ℹ️ No changes to push")
                
        except subprocess.CalledProcessError as e:
            print(f"❌ Git push failed: {e}")


def main():
    # Setup
    chrome_bookmarks_path = get_chrome_bookmarks_path()
    folder_to_watch = chrome_bookmarks_path.parent
    export_dir = Path.cwd() / "exported_bookmarks"
    
    print("🔖 Bookmark-Only Sync Monitor")
    print(f"👀 Watching: {folder_to_watch}")
    print(f"📁 Export to: {export_dir}")
    print("📋 Will only sync on actual bookmark changes (not navigation)")
    print("🛑 Press Ctrl+C to stop")
    print()
    
    # Create handler and observer
    event_handler = BookmarkOnlyHandler(export_dir)
    observer = Observer()
    observer.schedule(event_handler, path=str(folder_to_watch), recursive=False)
    
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping bookmark monitor...")
        observer.stop()
    
    observer.join()
    print("✅ Monitor stopped")


if __name__ == "__main__":
    main()