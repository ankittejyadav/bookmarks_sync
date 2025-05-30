import os
import shutil
import platform
import time
import psutil
from datetime import datetime
from pathlib import Path


def get_chrome_bookmarks_path():
    system = platform.system()
    if system == "Windows":
        return (
            Path(os.environ["LOCALAPPDATA"])
            / "Google/Chrome/User Data/Default/Bookmarks"
        )
    elif system == "Darwin":
        return (
            Path.home() / "Library/Application Support/Google/Chrome/Default/Bookmarks"
        )
    else:
        raise Exception("Unsupported OS")


def is_chrome_running():
    """Check if Chrome is currently running"""
    for proc in psutil.process_iter(['name']):
        try:
            if 'chrome' in proc.info['name'].lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def wait_for_file_access(file_path, max_wait=10):
    """Wait for file to be accessible for reading/writing"""
    for _ in range(max_wait * 10):  # Check every 100ms
        try:
            if os.path.exists(file_path):
                # Try to open file to check if it's accessible
                with open(file_path, 'r', encoding='utf-8') as f:
                    f.read(1)  # Try to read just 1 character
                return True
        except (PermissionError, OSError, UnicodeDecodeError):
            time.sleep(0.1)
            continue
        except Exception:
            # If it's some other error, file might still be accessible
            return True
    return False


def safe_copy_bookmarks(source, destination, max_retries=3):
    """Safely copy bookmarks file with retries"""
    for attempt in range(max_retries):
        try:
            # Wait for source file to be accessible
            if not wait_for_file_access(source):
                raise PermissionError(f"Cannot access source file: {source}")
            
            # Create backup of destination if it exists
            if destination.exists():
                backup_path = destination.with_suffix('.backup')
                shutil.copy2(destination, backup_path)
                print(f"📋 Created backup: {backup_path}")
            
            # Perform the copy
            shutil.copy2(source, destination)
            print(f"✅ Successfully copied bookmarks")
            return True
            
        except (PermissionError, OSError) as e:
            print(f"⚠️ Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(1)  # Wait before retry
            else:
                raise
    
    return False


def import_bookmarks(import_file):
    import_file = Path(import_file).expanduser()
    if not import_file.exists():
        print(f"❌ Import file not found: {import_file}")
        return False

    bookmarks_file = get_chrome_bookmarks_path()
    
    # Check if Chrome is running and warn user
    if is_chrome_running():
        print("⚠️ Chrome is running! This may cause permission issues.")
        print("💡 For best results, close Chrome before syncing bookmarks.")
        # Don't exit, just warn - sometimes it still works

    try:
        # Use safe copy with retries
        safe_copy_bookmarks(import_file, bookmarks_file)
        print(f"✅ Imported bookmarks from: {import_file}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to import bookmarks: {e}")
        return False


if __name__ == "__main__":
    # Default path to synced bookmark file
    import_file = Path.cwd() / "exported_bookmarks" / "Bookmark_Chrome.json"
    import_bookmarks(import_file)
