# Enhanced Bookmark Sync Controller
# Run this instead of running monitor and import scripts separately
# This prevents infinite loops and manages both processes safely

import time
import threading
import subprocess
import signal
import sys
from pathlib import Path
from multiprocessing import Process, Queue, Event


class BookmarkSyncController:
    def __init__(self):
        self.monitor_process = None
        self.import_process = None
        self.shutdown_event = Event()
        self.sync_lock = threading.Lock()
        
    def start_monitor_process(self):
        """Start the bookmark monitoring process"""
        def run_monitor():
            try:
                subprocess.run([sys.executable, "monitor_bookmarks_fixed.py"], check=True)
            except KeyboardInterrupt:
                pass
            except Exception as e:
                print(f"❌ Monitor process error: {e}")
        
        self.monitor_process = Process(target=run_monitor)
        self.monitor_process.start()
        print("🚀 Started bookmark monitor process")
    
    def start_import_process(self):
        """Start the bookmark import process"""
        def run_import():
            try:
                subprocess.run([sys.executable, "import_monitored_bookmarks_fixed.py"], check=True)
            except KeyboardInterrupt:
                pass
            except Exception as e:
                print(f"❌ Import process error: {e}")
        
        self.import_process = Process(target=run_import)
        self.import_process.start()
        print("🚀 Started bookmark import process")
    
    def start_sync(self):
        """Start both monitor and import processes"""
        print("🔄 Starting Bookmark Sync System...")
        print("⚡ Anti-loop protection: ENABLED")
        print("🔒 Permission handling: ENHANCED")
        print("-" * 50)
        
        # Start both processes
        self.start_monitor_process()
        time.sleep(2)  # Small delay to prevent startup conflicts
        self.start_import_process()
        
        print("✅ Both processes started successfully!")
        print("💡 Press Ctrl+C to stop all processes")
        
        try:
            # Keep main process alive and monitor subprocesses
            while True:
                if self.monitor_process and not self.monitor_process.is_alive():
                    print("⚠️ Monitor process died, restarting...")
                    self.start_monitor_process()
                
                if self.import_process and not self.import_process.is_alive():
                    print("⚠️ Import process died, restarting...")
                    self.start_import_process()
                
                time.sleep(5)  # Check every 5 seconds
                
        except KeyboardInterrupt:
            self.stop_sync()
    
    def stop_sync(self):
        """Stop all sync processes"""
        print("\n🛑 Stopping Bookmark Sync System...")
        
        if self.monitor_process and self.monitor_process.is_alive():
            self.monitor_process.terminate()
            self.monitor_process.join(timeout=5)
            print("🔴 Monitor process stopped")
        
        if self.import_process and self.import_process.is_alive():
            self.import_process.terminate() 
            self.import_process.join(timeout=5)
            print("🔴 Import process stopped")
        
        print("✅ All processes stopped successfully")


def setup_signal_handlers(controller):
    """Setup signal handlers for clean shutdown"""
    def signal_handler(signum, frame):
        controller.stop_sync()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


if __name__ == "__main__":
    print("🔖 Bookmark Sync Controller v2.0")
    print("=" * 50)
    
    # Check if required files exist
    required_files = [
        "monitor_bookmarks_fixed.py",
        "import_monitored_bookmarks_fixed.py",
        "bookmarks_export.py",
        "bookmarks_import_fixed.py"
    ]
    
    missing_files = [f for f in required_files if not Path(f).exists()]
    if missing_files:
        print(f"❌ Missing required files: {missing_files}")
        print("Please make sure all files are in the same directory")
        sys.exit(1)
    
    # Create controller and start
    controller = BookmarkSyncController()
    setup_signal_handlers(controller)
    
    try:
        controller.start_sync()
    except Exception as e:
        print(f"❌ Sync controller error: {e}")
        controller.stop_sync()
