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


class UltraPreciseBookmarkDetector(FileSystemEventHandler):
    def __init__(self, export_dir):
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        
        self.sync_lock = threading.Lock()
        self.processing = False
        self.last_sync_time = 0
        self.cooldown_period = 2
        
        # Multiple detection strategies
        chrome_bookmarks = get_chrome_bookmarks_path()
        self.file_path = chrome_bookmarks
        
        # Strategy 1: Bookmark counting
        self.last_bookmark_count = self.count_bookmarks()
        
        # Strategy 2: Core bookmark data hash
        self.last_core_hash = self.get_core_bookmark_hash()
        
        # Strategy 3: File size tracking (rough indicator)
        self.last_file_size = self.get_file_size()
        
        # Strategy 4: Timing analysis
        self.recent_changes = []  # Track recent file changes
        
        print(f"📊 Initial: {self.last_bookmark_count} bookmarks, {self.last_file_size} bytes")

    def get_file_size(self):
        """Get current file size"""
        try:
            return os.path.getsize(self.file_path) if os.path.exists(self.file_path) else 0
        except:
            return 0

    def count_bookmarks(self):
        """Count actual bookmarks (Strategy 1)"""
        try:
            if not os.path.exists(self.file_path):
                return 0
                
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            count = 0
            
            def count_recursive(node):
                nonlocal count
                if isinstance(node, dict):
                    if node.get('type') == 'url':
                        count += 1
                    if 'children' in node:
                        for child in node['children']:
                            count_recursive(child)
                    # Handle roots
                    if not node.get('type') and not node.get('children'):
                        for value in node.values():
                            if isinstance(value, dict):
                                count_recursive(value)
            
            if 'roots' in data:
                count_recursive(data['roots'])
            
            return count
            
        except Exception as e:
            print(f"❌ Count error: {e}")
            return 0

    def get_core_bookmark_hash(self):
        """Get hash of core bookmark data only (Strategy 2)"""
        try:
            if not os.path.exists(self.file_path):
                return None
                
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract minimal bookmark representation
            core_data = []
            
            def extract_core(node, path=""):
                if isinstance(node, dict):
                    if node.get('type') == 'url':
                        # Only store URL and name for bookmarks
                        core_data.append({
                            'url': node.get('url', ''),
                            'name': node.get('name', ''),
                            'path': path
                        })
                    elif node.get('type') == 'folder':
                        # Store folder name and path
                        folder_path = f"{path}/{node.get('name', '')}" if path else node.get('name', '')
                        core_data.append({
                            'type': 'folder',
                            'name': node.get('name', ''),
                            'path': folder_path
                        })
                        if 'children' in node:
                            for child in node['children']:
                                extract_core(child, folder_path)
                    elif 'children' in node:
                        for child in node['children']:
                            extract_core(child, path)
                    elif not node.get('type'):
                        # Root level processing
                        for key, value in node.items():
                            if key in ['bookmark_bar', 'other', 'synced'] and isinstance(value, dict):
                                extract_core(value, key)
            
            if 'roots' in data:
                extract_core(data['roots'])
            
            # Sort for consistent hashing
            core_data.sort(key=lambda x: (x.get('path', ''), x.get('name', ''), x.get('url', '')))
            
            core_json = json.dumps(core_data, sort_keys=True)
            return hashlib.md5(core_json.encode()).hexdigest()
            
        except Exception as e:
            print(f"❌ Hash error: {e}")
            return None

    def analyze_change_pattern(self):
        """Analyze timing pattern of recent changes (Strategy 4)"""
        current_time = time.time()
        
        # Clean old changes (keep only last 30 seconds)
        self.recent_changes = [t for t in self.recent_changes if current_time - t < 30]
        
        # Add current change
        self.recent_changes.append(current_time)
        
        # Analyze pattern
        if len(self.recent_changes) < 2:
            return "single_change"
        
        # Check intervals between changes
        intervals = []
        for i in range(1, len(self.recent_changes)):
            intervals.append(self.recent_changes[i] - self.recent_changes[i-1])
        
        avg_interval = sum(intervals) / len(intervals)
        
        # Navigation tends to cause very frequent small changes
        if len(self.recent_changes) > 3 and avg_interval < 1:
            return "rapid_navigation"  # Likely navigation
        elif len(self.recent_changes) <= 2 and avg_interval > 2:
            return "user_action"  # Likely bookmark action
        else:
            return "uncertain"

    def is_significant_size_change(self, new_size):
        """Check if file size change is significant (Strategy 3)"""
        if self.last_file_size == 0:
            return True
            
        size_diff = abs(new_size - self.last_file_size)
        size_change_percent = (size_diff / self.last_file_size) * 100
        
        # Bookmark changes usually cause larger size changes
        # Navigation changes are typically small (metadata updates)
        return size_change_percent > 0.1 or size_diff > 100

    def detect_bookmark_changes(self):
        """Multi-strategy bookmark change detection"""
        try:
            # Get current values
            current_count = self.count_bookmarks()
            current_hash = self.get_core_bookmark_hash()
            current_size = self.get_file_size()
            
            # Strategy 1: Count change (most reliable)
            count_changed = current_count != self.last_bookmark_count
            
            # Strategy 2: Core data hash change
            hash_changed = current_hash != self.last_core_hash
            
            # Strategy 3: Significant size change
            size_significant = self.is_significant_size_change(current_size)
            
            # Strategy 4: Change pattern analysis
            change_pattern = self.analyze_change_pattern()
            
            # Decision logic
            confidence_score = 0
            reasons = []
            
            if count_changed:
                confidence_score += 100  # Highest confidence
                reasons.append(f"Count: {self.last_bookmark_count} → {current_count}")
            
            if hash_changed:
                confidence_score += 80
                reasons.append("Core bookmark data changed")
            
            if size_significant:
                confidence_score += 30
                size_diff = current_size - self.last_file_size
                reasons.append(f"Size: {size_diff:+d} bytes")
            
            # Pattern analysis modifier
            if change_pattern == "rapid_navigation":
                confidence_score -= 50  # Reduce confidence
                reasons.append("Pattern: Rapid navigation detected")
            elif change_pattern == "user_action":
                confidence_score += 20
                reasons.append("Pattern: User action detected")
            
            # Update stored values
            self.last_bookmark_count = current_count
            self.last_core_hash = current_hash
            self.last_file_size = current_size
            
            # Decision threshold
            is_bookmark_change = confidence_score >= 70
            
            return is_bookmark_change, confidence_score, reasons
            
        except Exception as e:
            print(f"❌ Detection error: {e}")
            return False, 0, [f"Error: {e}"]

    def on_modified(self, event):
        if event.is_directory or self.processing:
            return

        if not event.src_path.endswith("Bookmarks"):
            return
            
        current_time = time.time()
        if current_time - self.last_sync_time < self.cooldown_period:
            return
        
        with self.sync_lock:
            if self.processing:
                return
                
            self.processing = True
            
            try:
                # Wait for file stability
                time.sleep(0.5)
                
                print("🔍 Multi-strategy analysis...")
                
                is_change, confidence, reasons = self.detect_bookmark_changes()
                
                print(f"📊 Confidence Score: {confidence}")
                for reason in reasons:
                    print(f"   • {reason}")
                
                if not is_change:
                    print("📄 Not a bookmark change (likely navigation/metadata)")
                    return
                
                print("🔥 BOOKMARK CHANGE CONFIRMED!")
                
                # Export and sync
                export_bookmarks(self.export_dir)
                self.git_push_changes()
                
                self.last_sync_time = current_time
                print("✅ Sync completed")
                
            except Exception as e:
                print(f"❌ Error: {e}")
            finally:
                self.processing = False

    def git_push_changes(self):
        """Push to git"""
        try:
            result = subprocess.run(["git", "status", "--porcelain"], 
                                  capture_output=True, text=True, cwd=self.export_dir.parent)
            
            if result.stdout.strip():
                subprocess.run(["git", "add", "."], check=True, cwd=self.export_dir.parent)
                subprocess.run(["git", "commit", "-m", "🎯 Confirmed bookmark change"], 
                             check=True, cwd=self.export_dir.parent)
                subprocess.run(["git", "push"], check=True, cwd=self.export_dir.parent)
                print("🚀 Pushed to Git")
            else:
                print("ℹ️ No changes to push")
                
        except subprocess.CalledProcessError as e:
            print(f"❌ Git push failed: {e}")


def main():
    chrome_bookmarks_path = get_chrome_bookmarks_path()
    folder_to_watch = chrome_bookmarks_path.parent
    export_dir = Path.cwd() / "exported_bookmarks"
    
    print("🎯 Ultra-Precise Bookmark Detector")
    print("🧠 Multi-Strategy Detection:")
    print("   1. Bookmark count tracking")
    print("   2. Core bookmark data hashing")
    print("   3. File size analysis")
    print("   4. Change pattern recognition")
    print(f"👀 Watching: {folder_to_watch}")
    print(f"📁 Export to: {export_dir}")
    print("🛑 Press Ctrl+C to stop")
    print()
    
    detector = UltraPreciseBookmarkDetector(export_dir)
    observer = Observer()
    observer.schedule(detector, path=str(folder_to_watch), recursive=False)
    
    observer.start()
    
    try:
        print("✅ Ultra-precise monitoring active!")
        print("Test it:")
        print("   • Navigate websites → Should NOT sync")
        print("   • Add bookmark → SHOULD sync")
        print("   • Delete bookmark → SHOULD sync")
        print()
        
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping detector...")
        observer.stop()
    
    observer.join()
    print("✅ Stopped")


if __name__ == "__main__":
    main()