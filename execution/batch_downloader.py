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
    )
except ImportError:
    from driver_utils import (
        load_brightspace_cookies,
        setup_driver,
        validate_and_refresh_session,
    )
    from kaltura_video_extractor import extract_and_download, extract_pdf_content

# Project Root Setup
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE_FILE = os.path.join(PROJECT_ROOT, "download_queue.json")

def main():
    if not os.path.exists(QUEUE_FILE):
        print(f"Queue file '{QUEUE_FILE}' not found. Run brightspace_parser.py first.")
        sys.exit(1)

    print(f"Loading queue from {QUEUE_FILE}...")
    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        queue = json.load(f)

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
            print(f"Target: {target_dir}")
            
            try:
                item_type = item.get("type", "video") # Default to video for backward compatibility
                
                if item_type == "pdf":
                    extract_pdf_content(driver, url, target_dir)
                else:
                    extract_and_download(driver, url, target_dir)
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
