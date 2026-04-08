import json
import os
import re
import sys
import time

import undetected_chromedriver as uc
from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from seleniumwire import webdriver

# User-Agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"

# Configuration
DOWNLOAD_PDFS = True # Set to False to skip PDF downloads

# Project Root Setup
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOWNLOADS_DIR = os.path.join(PROJECT_ROOT, "downloads")
QUEUE_FILE = os.path.join(PROJECT_ROOT, "download_queue.json")
HISTORY_FILE = os.path.join(PROJECT_ROOT, "download_history.json")
REPORT_FILE = os.path.join(PROJECT_ROOT, "video_titles.txt")

try:
    from execution.driver_utils import (
        load_brightspace_cookies,
        setup_driver,
        validate_and_refresh_session,
    )
    from execution.kaltura_video_extractor import (
        extract_and_download,
        sanitize_filename,
    )
except ImportError:
    from driver_utils import (
        load_brightspace_cookies,
        setup_driver,
        validate_and_refresh_session,
    )
    from kaltura_video_extractor import extract_and_download, sanitize_filename

def find_all_elements_shadow(driver, selector, only_visible=True):
    """
    Finds elements using a CSS selector, traversing through all open Shadow DOM roots recursively.
    """
    script = f"""
    function findInShadow(root, selector, onlyVisible, results = []) {{
        if (!root) return results;
        
        // Find matching descendants in current root
        try {{
            let elements = root.querySelectorAll(selector);
            for (let el of elements) {{
                let isVisible = (el.offsetParent !== null);
                if (!onlyVisible || isVisible) {{
                    results.push(el);
                }}
            }}
        }} catch(e) {{}}

        // Recurse into all shadow roots
        let all = root.querySelectorAll('*');
        for (let el of all) {{
            if (el.shadowRoot) {{
                findInShadow(el.shadowRoot, selector, onlyVisible, results);
            }}
        }}
        return results;
    }}
    return findInShadow(document, '{selector}', {str(only_visible).lower()});
    """
    return driver.execute_script(script)

def main():
    # Run headless for speed and convenience
    driver = setup_driver(headless=True)
    try:
        load_brightspace_cookies(driver)
        
        print("Navigating to Brightspace Homepage...")
        driver.get("https://purdue.brightspace.com/")
        
        # Validate Session and Auto-Login if needed
        driver = validate_and_refresh_session(driver)
        
        # Wait for content to load
        time.sleep(5) 

        print("Searching for 'Pinned' tab...")
        pinned_tab = None
        
        find_tabs_script = """
        function collectTabs(root = document, tabs = []) {
            root.querySelectorAll('d2l-tab, d2l-tab-internal').forEach(el => tabs.push(el));
            root.querySelectorAll('*').forEach(el => {
                if (el.shadowRoot) collectTabs(el.shadowRoot, tabs);
            });
            return tabs;
        }
        return collectTabs();
        """
        
        for attempt in range(30):
            try:
                all_tabs = driver.execute_script(find_tabs_script)
                for tab in all_tabs:
                    t_text = tab.get_attribute("text")
                    t_title = tab.get_attribute("title")
                    t_id = tab.get_attribute("id")
                    
                    if (t_id and "pinned" in t_id.lower()) or (t_text and "Pinned" in t_text) or (t_title and "Pinned" in t_title):
                        pinned_tab = tab
                        break
                if pinned_tab: break
            except: pass
            time.sleep(1)
            
        if not pinned_tab:
            print("Could not find 'Pinned' tab.")
            driver.save_screenshot("error_tab_not_found.png")
            return

        print("Found 'Pinned' tab. Clicking...")
        driver.execute_script("arguments[0].click();", pinned_tab)
        time.sleep(5) # Give it plenty of time to switch and render cards

        print("Extracting course links...")
        enrollment_cards = []
        # Target the newer tag name which was discovered during debugging
        for _ in range(10):
             enrollment_cards = find_all_elements_shadow(driver, 'd2l-my-courses-enrollment-card', only_visible=True)
             if not enrollment_cards:
                 enrollment_cards = find_all_elements_shadow(driver, 'd2l-enrollment-card', only_visible=True)
             
             if enrollment_cards:
                 break
             time.sleep(1)
             
        if not enrollment_cards:
            print("No visible enrollment cards found. Checking for hidden ones...")
            enrollment_cards = find_all_elements_shadow(driver, 'd2l-my-courses-enrollment-card', only_visible=False)
            if not enrollment_cards:
                enrollment_cards = find_all_elements_shadow(driver, 'd2l-enrollment-card', only_visible=False)
            
            if not enrollment_cards:
                print("Aborting: No enrollment cards found.")
                driver.save_screenshot("debug_final_fail.png")
                return
            else:
                print("Proceeding with layout-less/hidden cards as fallback.")
        
        print(f"Found {len(enrollment_cards)} enrollment cards.")
        
        # Initialize Download Queue
        download_queue = []
        
        # Load History
        history_set = set()
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    history_set = set(json.load(f))
            except Exception:
                history_set = set()
        
        # Initialize/Clear the output file
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            f.write("Brightspace Video Extraction Report\n")
            f.write("===================================\n\n")

        # Link extraction script
        get_link_script = """
        function getLink(el) {
            function search(root) {
                if (!root) return null;
                let a = root.querySelector('a[href*="/d2l/home/"]');
                if (a) return a.href;
                let children = root.querySelectorAll('*');
                for (let child of children) {
                    if (child.shadowRoot) {
                        let res = search(child.shadowRoot);
                        if (res) return res;
                    }
                }
                return null;
            }
            return search(el.shadowRoot);
        }
        return getLink(arguments[0]);
        """
        
        unique_links = set()
        for card in enrollment_cards:
            try:
                href = driver.execute_script(get_link_script, card)
                if href and href not in unique_links:
                    unique_links.add(href)
                    print(f"Course Link: {href}")
            except: pass

        print(f"\nProcessing {len(unique_links)} courses...")
        for course_url in unique_links:
            try:
                if "/d2l/home/" in course_url:
                    content_url = course_url.replace("/d2l/home/", "/d2l/le/content/") + "/Home"
                else: continue
                    
                print(f"\nNavigating to Content: {content_url}")
                driver.get(content_url)
                time.sleep(5)

                try:
                    title_elem = driver.find_element(By.CSS_SELECTOR, ".d2l-navigation-s-title-container a")
                    title = title_elem.get_attribute("title")
                    print(f"Course: {title}")
                    with open(REPORT_FILE, "a", encoding="utf-8") as f:
                        f.write(f"\n{'='*50}\nCOURSE: {title}\n{'='*50}\n")
                except: title = "Unknown Course"

                # Content extraction
                try:
                    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "D2L_LE_Content_TreeBrowser")))
                    items = driver.find_elements(By.CSS_SELECTOR, ".d2l-le-TreeAccordionItem-anchor")
                    module_indices = [i for i, item in enumerate(items) if "module" in item.get_attribute("textContent").lower()]
                    
                    path_stack = [] 
                    with open(REPORT_FILE, "a", encoding="utf-8") as f:
                        for index in module_indices:
                             items = driver.find_elements(By.CSS_SELECTOR, ".d2l-le-TreeAccordionItem-anchor")
                             if index >= len(items): continue
                             item = items[index]
                             module_name = item.get_attribute("textContent").strip().splitlines()[0].strip()
                             
                             # Hierarchy logic (simplified)
                             if "Module" in module_name: path_stack = [module_name]
                             elif "Topic" in module_name and path_stack: 
                                 if len(path_stack) > 1: path_stack.pop()
                                 path_stack.append(module_name)
                             else: path_stack = [module_name]

                             module_path = os.path.join(*[sanitize_filename(p) for p in path_stack])
                             print(f"  Processing: {module_path}")
                             f.write(f"\n  MODULE: {module_path}\n  {'-'*len(module_path)}\n")
                             
                             driver.execute_script("arguments[0].scrollIntoView(true);", item)
                             driver.execute_script("arguments[0].click();", item)
                             time.sleep(5) 
                             
                             video_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/viewContent/']")
                             unique_vids = set()
                             for vid in video_links:
                                 v_href = vid.get_attribute("href")
                                 v_text = vid.text.strip() or (vid.get_attribute("title") or "").replace(" - External Learning Tool", "").strip()
                                 
                                 tag = "[OTHER]"
                                 v_low = v_text.lower()
                                 if "pdf" in v_low or "slides" in v_low: tag = "[PDF]"
                                 elif "external learning tool" in (vid.get_attribute("title") or "").lower() or re.search(r'\(\d+:\d+\)', v_text): tag = "[VIDEO]"
                                 
                                 if v_href and v_href not in unique_vids:
                                     unique_vids.add(v_href)
                                     f.write(f"    - {tag} {v_text}\n")
                                     if v_href in history_set: continue

                                     content_type = "pdf" if tag == "[PDF]" else "video" if tag == "[VIDEO]" else None
                                     if content_type and (content_type == "video" or DOWNLOAD_PDFS):
                                         target_dir = os.path.join(DOWNLOADS_DIR, sanitize_filename(title), module_path, "pdfs" if content_type == "pdf" else "videos")
                                         download_queue.append({"title": v_text, "url": v_href, "target_dir": target_dir, "type": content_type})
                except Exception as e: print(f"  Error: {e}")
            except Exception as e: print(f"Error: {e}")

        # Save Queue
        unique_queue_map = {}
        for item in download_queue:
            depth = item['target_dir'].count(os.sep)
            if item['url'] not in unique_queue_map or depth > unique_queue_map[item['url']]['depth']:
                unique_queue_map[item['url']] = {**item, 'depth': depth}
        
        final_queue = [{k: v for k, v in item.items() if k != 'depth'} for item in unique_queue_map.values()]
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(final_queue, f, indent=2)
        print(f"\nSaved {len(final_queue)} items to queue.")

    except Exception as e:
        print(f"An error occurred: {e}")
        driver.save_screenshot("error_screenshot.png")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
