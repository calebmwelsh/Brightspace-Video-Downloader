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
    from execution.kaltura_video_extractor import extract_and_download
except ImportError:
    from driver_utils import (
        load_brightspace_cookies,
        setup_driver,
        validate_and_refresh_session,
    )
    from kaltura_video_extractor import extract_and_download

def main():
    queue_file = "download_queue.json"
    if not os.path.exists(queue_file):
        print(f"Queue file '{queue_file}' not found. Run brightspace_parser.py first.")
        sys.exit(1)

    print(f"Loading queue from {queue_file}...")
    with open(queue_file, "r", encoding="utf-8") as f:
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
            title = item.get("title")
            
            print(f"\n[{i+1}/{len(queue)}] Processing: {title}")
            print(f"Target: {target_dir}")
            
            try:
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
