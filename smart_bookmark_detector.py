import time
import subprocess
import threading
import hashlib
import json
import os
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from bookmarks_export import export_bookmarks, get_chrome_bookmarks_path


class SmartBookmarkDetector(FileSystemEventHandler):
    def __init__(self, export_dir):
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        
        self.sync_lock = threading.Lock()
        self.processing = False
        self.last_sync_time = 0
        self.cooldown_period = 3  # 3 seconds between checks
        
        # Store bookmark counts and structure
        chrome_bookmarks = get_chrome_bookmarks_path()
        self.last_bookmark_count = self.count_bookmarks(chrome_bookmarks)
        self.last_bookmark_urls = self.get_all_bookmark_urls(chrome_bookmarks)
        self.last_folder_structure = self.get_folder_structure(chrome_bookmarks)
        
        print(f"📊 Initial state: {self.last_bookmark_count} bookmarks")
        print(f"📁 Initial folders: {len(self.last_folder_structure)} folders")

    def count_bookmarks(self, filepath):
        """Count total number of actual bookmarks (not folders)"""
        try:
            if not Path(filepath).exists():
                return 0
                
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return self._count_bookmarks_recursive(data.get('roots', {}))
            
        except Exception as e:
            print(f"❌ Error counting bookmarks: {e}")
            return 0

    def _count_bookmarks_recursive(self, node):
        """Recursively count bookmarks"""
        count = 0
        
        if isinstance(node, dict):
            # If this is a bookmark (has URL), count it
            if node.get('type') == 'url' and 'url' in node:
                count += 1
            
            # Process children
            if 'children' in node:
                for child in node['children']:
                    count += self._count_bookmarks_recursive(child)
            
            # Process roots
            if not any(key in node for key in ['type', 'children']):
                for key, value in node.items():
                    count += self._count_bookmarks_recursive(value)
        
        return count

    def get_all_bookmark_urls(self, filepath):
        """Get set of all bookmark URLs"""
        try:
            if not Path(filepath).exists():
                return set()
                
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            urls = set()
            self._collect_urls_recursive(data.get('roots', {}), urls)
            return urls
            
        except Exception as e:
            print(f"❌ Error getting URLs: {e}")
            return set()

    def _collect_urls_recursive(self, node, urls):
        """Recursively collect all bookmark URLs"""
        if isinstance(node, dict):
            # If this is a bookmark, add its URL
            if node.get('type') == 'url' and 'url' in node:
                urls.add(node['url'])
            
            # Process children
            if 'children' in node:
                for child in node['children']:
                    self._collect_urls_recursive(child, urls)
            
            # Process roots
            if not any(key in node for key in ['type', 'children']):
                for key, value in node.items():
                    self._collect_urls_recursive(value, urls)

    def get_folder_structure(self, filepath):
        """Get folder names and their paths"""
        try:
            if not Path(filepath).exists():
                return set()
                
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            folders = set()
            self._collect_folders_recursive(data.get('roots', {}), folders, "")
            return folders
            
        except Exception as e:
            print(f"❌ Error getting folders: {e}")
            return set()

    def _collect_folders_recursive(self, node, folders, path):
        """Recursively collect folder structure"""
        if isinstance(node, dict):
            # If this is a folder, add it
            if node.get('type') == 'folder' and 'name' in node:
                folder_path = f"{path}/{node['name']}" if path else node['name']
                folders.add(folder_path)
                
                # Process children with updated path
                if 'children' in node:
                    for child in node['children']:
                        self._collect_folders_recursive(child, folders, folder_path)
            
            # Process children for non-folder nodes
            elif 'children' in node:
                for child in node['children']:
                    self._collect_folders_recursive(child, folders, path)
            
            # Process roots
            elif not any(key in node for key in ['type', 'children']):
                for key, value in node.items():
                    if key in ['bookmark_bar', 'other', 'synced']:
                        self._collect_folders_recursive(value, folders, key)

    def detect_bookmark_changes(self, filepath):
        """Detect if actual bookmark changes occurred"""
        try:
            # Get current state
            current_count = self.count_bookmarks(filepath)
            current_urls = self.get_all_bookmark_urls(filepath)
            current_folders = self.get_folder_structure(filepath)
            
            # Compare counts
            count_changed = current_count != self.last_bookmark_count
            
            # Compare URLs
            urls_changed = current_urls != self.last_bookmark_urls
            
            # Compare folder structure
            folders_changed = current_folders != self.last_folder_structure
            
            changes = []
            if count_changed:
                diff = current_count - self.last_bookmark_count
                changes.append(f"Count: {self.last_bookmark_count} → {current_count} ({diff:+d})")
            
            if urls_changed:
                added_urls = current_urls - self.last_bookmark_urls
                removed_urls = self.last_bookmark_urls - current_urls
                if added_urls:
                    changes.append(f"Added URLs: {len(added_urls)}")
                if removed_urls:
                    changes.append(f"Removed URLs: {len(removed_urls)}")
            
            if folders_changed:
                added_folders = current_folders - self.last_folder_structure
                removed_folders = self.last_folder_structure - current_folders
                if added_folders:
                    changes.append(f"Added folders: {len(added_folders)}")
                if removed_folders:
                    changes.append(f"Removed folders: {len(removed_folders)}")
            
            # Update stored state
            self.last_bookmark_count = current_count
            self.last_bookmark_urls = current_urls
            self.last_folder_structure = current_folders
            
            return len(changes) > 0, changes
            
        except Exception as e:
            print(f"❌ Error detecting changes: {e}")
            return False, []

    def on_modified(self, event):
        if event.is_directory or self.processing:
            return

        # Only process main Bookmarks file
        if not event.src_path.endswith("Bookmarks"):
            return
            
        # Skip if in cooldown
        current_time = time.time()
        if current_time - self.last_sync_time < self.cooldown_period:
            return
        
        with self.sync_lock:
            if self.processing:
                return
                
            self.processing = True
            
            try:
                # Wait for file to stabilize
                time.sleep(1)
                
                print("🔍 Analyzing bookmark changes...")
                
                # Detect actual bookmark changes
                has_changes, changes = self.detect_bookmark_changes(event.src_path)
                
                if not has_changes:
                    print("📄 No bookmark changes detected (navigation/metadata only)")
                    return
                
                print("🔥 BOOKMARK CHANGES DETECTED!")
                for change in changes:
                    print(f"   • {change}")
                
                # Export and sync
                export_bookmarks(self.export_dir)
                self.git_push_changes()
                
                self.last_sync_time = current_time
                print("✅ Bookmark sync completed")
                
            except Exception as e:
                print(f"❌ Sync error: {e}")
            finally:
                self.processing = False

    def git_push_changes(self):
        """Push changes to git"""
        try:
            # Check if there are changes
            result = subprocess.run(["git", "status", "--porcelain"], 
                                  capture_output=True, text=True, cwd=self.export_dir.parent)
            
            if result.stdout.strip():
                subprocess.run(["git", "add", "."], check=True, cwd=self.export_dir.parent)
                subprocess.run(["git", "commit", "-m", "🔖 Bookmark structure changed"], 
                             check=True, cwd=self.export_dir.parent)
                subprocess.run(["git", "push"], check=True, cwd=self.export_dir.parent)
                print("🚀 Pushed to Git")
            else:
                print("ℹ️ No file changes to push")
                
        except subprocess.CalledProcessError as e:
            print(f"❌ Git push failed: {e}")


def main():
    # Setup
    chrome_bookmarks_path = get_chrome_bookmarks_path()
    folder_to_watch = chrome_bookmarks_path.parent
    export_dir = Path.cwd() / "exported_bookmarks"
    
    print("🎯 Smart Bookmark Change Detector")
    print(f"👀 Watching: {folder_to_watch}")
    print(f"📁 Export to: {export_dir}")
    print("🧠 Uses intelligent change detection:")
    print("   • Counts total bookmarks")
    print("   • Tracks all bookmark URLs")
    print("   • Monitors folder structure")
    print("   • Ignores navigation/metadata changes")
    print("🛑 Press Ctrl+C to stop")
    print()
    
    # Test current state
    detector = SmartBookmarkDetector(export_dir)
    
    # Create observer
    observer = Observer()
    observer.schedule(detector, path=str(folder_to_watch), recursive=False)
    
    observer.start()
    
    try:
        print("✅ Monitoring started. Try:")
        print("   • Navigate to websites (should NOT trigger)")
        print("   • Add/remove bookmarks (SHOULD trigger)")
        print("   • Create/delete folders (SHOULD trigger)")
        print()
        
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping detector...")
        observer.stop()
    
    observer.join()
    print("✅ Detector stopped")


if __name__ == "__main__":
    main()