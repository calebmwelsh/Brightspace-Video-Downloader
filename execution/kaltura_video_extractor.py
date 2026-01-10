import argparse
import os
import re
import string
import sys
import time

import requests
import undetected_chromedriver as uc
from dotenv import load_dotenv
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from seleniumwire import webdriver

# User-Agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"

def sanitize_filename(name):
    # Remove or replace characters not allowed in filenames
    valid_chars = f"-_.() {string.ascii_letters}{string.digits}"
    return ''.join(c if c in valid_chars else '_' for c in name).strip()

try:
    from execution.driver_utils import load_brightspace_cookies, setup_driver
except ImportError:
    from driver_utils import load_brightspace_cookies, setup_driver


def set_brightspace_cookies(driver):
    load_brightspace_cookies(driver)
    

def extract_and_download(driver, page_url, download_dir):
    # Record the current number of requests before loading the page
    start_idx = len(driver.requests)
    print(f"Current requests: {start_idx}")
    print(f"Visiting: {page_url}")
    driver.get(page_url)

    time.sleep(10)  # Wait for network requests to be made after play

    # Only look at new requests
    new_requests = driver.requests[start_idx:]
    print(f"New requests: {len(new_requests)}")

    # Extract the page title for filename
    try:
        title_elem = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "d2l-page-title"))
        )
        page_title = title_elem.text
        if not page_title:
            # Try to get from heading if empty
            heading_elem = driver.find_element(By.CLASS_NAME, "vui-heading-1")
            page_title = heading_elem.text
    except Exception as e:
        print(f"Could not extract page title: {e}")
        page_title = "video"
    
    safe_title = sanitize_filename(page_title)
    seg_url = None
    
    # Save all requests to a CSV file for inspection (optional, keeping for debug)
    # requests_data = [] 
    # Implementation omitted for brevity as it was commented out in original

    csv_path = os.path.join(download_dir, f"requests_dump_{int(time.time())}.csv")
    # print(f"Requests saved to {csv_path}") 

    for request in new_requests:
        if request.response and "-v1-a1.ts" in request.url:
            seg_url = request.url
            print(f"Found segment URL: {seg_url}")
            break
            
    if not seg_url:
        print("No segment URL found on this page.")
        return

    # Modify the URL: replace first 'hls' with 'pd'
    new_url = seg_url.replace("hls", "pd", 1)
    print(f"Modified URL: {new_url}")

    # Use flat output directory
    os.makedirs(download_dir, exist_ok=True)
    filename = os.path.join(download_dir, f"{safe_title}.mp4")
    print(f"Downloading to: {filename}")
    
    headers = {"User-Agent": USER_AGENT}
    with requests.get(new_url, headers=headers, stream=True) as r:
        r.raise_for_status()
        with open(filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    print("Download complete.")

def main():
    parser = argparse.ArgumentParser(description="Extract Kaltura videos from Brightspace.")
    parser.add_argument("--urls", nargs="+", required=True, help="List of Brightspace video page URLs to scrape.")
    parser.add_argument("--output-dir", default="downloads", help="Directory to save downloaded videos.")
    
    args = parser.parse_args()

    # Create output directory if it doesn't exist
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    driver = setup_driver()
    try:
        set_brightspace_cookies(driver)
        for link in args.urls:
            extract_and_download(driver, link, args.output_dir)
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
