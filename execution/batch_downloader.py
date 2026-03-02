import json
import os
import sys
import time

try:
    from execution.driver_utils import (
        load_brightspace_cookies,
        setup_driver,
        validate_and_refresh_session,
    )
    from execution.kaltura_video_extractor import (
        extract_and_download,
        extract_pdf_content,
        sanitize_filename,
    )
except ImportError:
    from driver_utils import (
        load_brightspace_cookies,
        setup_driver,
        validate_and_refresh_session,
    )
    from kaltura_video_extractor import (
        extract_and_download,
        extract_pdf_content,
        sanitize_filename,
    )

# Project Root Setup
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE_FILE = os.path.join(PROJECT_ROOT, "download_queue.json")
HISTORY_FILE = os.path.join(PROJECT_ROOT, "download_history.json")

def main():
    if not os.path.exists(QUEUE_FILE):
        print(f"Queue file '{QUEUE_FILE}' not found. Run brightspace_parser.py first.")
        sys.exit(1)

    print(f"Loading queue from {QUEUE_FILE}...")
    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        queue = json.load(f)

    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []
    history_set = set(history) # Faster lookup

    if not queue:
        print("Queue is empty.")
        return

    print(f"Found {len(queue)} items to download.")
    
    # Setup Driver (Headless!)
    print("Starting Headless Driver...")
    driver = setup_driver(headless=True)
    
    try:
        load_brightspace_cookies(driver)
        # load_brightspace_cookies already does driver.get("https://purdue.brightspace.com")
        
        # Validate Session
        driver = validate_and_refresh_session(driver)
        
        for i, item in enumerate(queue):
            url = item.get("url")
            target_dir = item.get("target_dir")
            
            # Fix relative paths to be absolute relative to PROJECT_ROOT
            if target_dir and not os.path.isabs(target_dir):
                # If path starts with "downloads", strip it to avoid duplication if we are already in root
                # actually, simpler: just join PROJECT_ROOT with the path
                target_dir = os.path.join(PROJECT_ROOT, target_dir)
                
            title = item.get("title")
            
            print(f"\n[{i+1}/{len(queue)}] Processing: {title}")
            
            if url in history_set:
                print(f"Skipping (Already in history): {title}")
                continue

            # Check File Existence
            try:
                item_type = item.get("type", "video")
                safe_title = sanitize_filename(title)
                ext = ".pdf" if item_type == "pdf" else ".mp4"
                expected_path = os.path.join(target_dir, safe_title + ext)
                
                if os.path.exists(expected_path):
                    print(f"Skipping (File exists): {expected_path}")
                    history_set.add(url)
                    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                        json.dump(list(history_set), f, indent=2)
                    continue
            except Exception as e:
                print(f"Warning: Could not check file existence: {e}")

            print(f"Target: {target_dir}")
            
            try:
                item_type = item.get("type", "video") # Default to video for backward compatibility
                
                success = False
                if item_type == "pdf":
                    success = extract_pdf_content(driver, url, target_dir)
                else:
                    success = extract_and_download(driver, url, target_dir)

                if success:
                    history_set.add(url)
                    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                        json.dump(list(history_set), f, indent=2)
                    print(f"Successfully downloaded and added to history: {title}")
            except Exception as e:
                print(f"Error downloading {title}: {e}")
                # Optional: mark as failed in a separate file? 
                with open("failed_downloads.txt", "a", encoding="utf-8") as f:
                    f.write(f"{title} | {url} | {e}\n")

    finally:
        driver.quit()
        print("\nBatch download complete.")

if __name__ == "__main__":
    main()
