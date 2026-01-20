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


def find_element_shadow(driver, selector):
    """
    Finds an element using a CSS selector, traversing through open Shadow DOM roots.
    This is a simplified generic finder.
    """
    # ... (rest of function unchanged, just need to preserve it if I mistakenly targeted it)
    # Actually I should be careful not to replace the whole file if I can avoid it.
    # But since the imports are at the top and the logic is deep down, I might need two chunks or one big replace if I want to be safe?
    # No, let's just do imports first.

# Wait, I can't do multiple replace calls in one step unless I use multi_replace.
# I will use multi_replace_file_content.



# find_element_shadow is now imported from driver_utils
# We keep this comment or just remove the function entirely.
# The previous step imported it, so we can delete this block.

def find_all_elements_shadow(driver, selector):
    """
    Finds authentication elements using a CSS selector, traversing through open Shadow DOM roots.
    Filters out elements that are not visible (e.g. hidden tabs).
    """
    script = f"""
    function findElements(selector, root = document, results = []) {{
        // Check current root
        let elements = root.querySelectorAll(selector);
        for(let el of elements) {{
            // Check visibility: offsetParent is null if hidden (in most cases)
            // or use specific checkVisibility if supported, but offsetParent is robust for simple display:none
            if (el.offsetParent !== null) {{
                 results.push(el);
            }}
        }}
        
        // Check all children with shadowRoots
        let allNodes = root.querySelectorAll('*');
        for (let el of allNodes) {{
            if (el.shadowRoot) {{
                findElements(selector, el.shadowRoot, results);
            }}
        }}
        return results;
    }}
    return findElements('{selector}');
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

        print("Looking for 'Pinned' tab in Shadow DOM...")
        # Robust Pinned Tab Search: Find ALL tabs and filter in Python
        # This avoids issues with CSS attribute selectors in Shadow DOM
        pinned_tab = None
        
        # Script to find all d2l-tab-internal elements
        find_tabs_script = """
        function collectTabs(root = document, tabs = []) {
            root.querySelectorAll('d2l-tab-internal').forEach(el => tabs.push(el));
            root.querySelectorAll('*').forEach(el => {
                if (el.shadowRoot) collectTabs(el.shadowRoot, tabs);
            });
            return tabs;
        }
        return collectTabs();
        """
        
        print("Searching for 'Pinned' tab (Robust Method)...")
        for attempt in range(30):
            try:
                all_tabs = driver.execute_script(find_tabs_script)
                for tab in all_tabs:
                    # Check attributes
                    t_text = tab.get_attribute("text")
                    t_title = tab.get_attribute("title")
                    
                    if (t_text and "Pinned" in t_text) or (t_title and "Pinned" in t_title):
                        pinned_tab = tab
                        break
                
                if pinned_tab:
                    break
            except Exception as e:
                # Script execution might fail if page is reloading
                pass
            
            time.sleep(1)
            
        if not pinned_tab:
            print("Could not find 'Pinned' tab.")
            print(f"Debug: Current URL: {driver.current_url}")
            print(f"Debug: Current Title: {driver.title}")
            
            # Re-run collection safely to see what we DID find
            try:
                debug_tabs = driver.execute_script(find_tabs_script)
                print(f"Debug: Found {len(debug_tabs)} tabs total in DOM.")
                for dt in debug_tabs[:5]: # Print first 5
                     print(f" - Tab: text='{dt.get_attribute('text')}', title='{dt.get_attribute('title')}'")
            except Exception as e:
                print(f"Debug: Failed to list tabs: {e}")

            driver.save_screenshot("error_tab_not_found.png")
            return

        print("Found 'Pinned' tab. Clicking...")
        # Selenium click might fail if element is in shadow root or obscured, use JS click
        driver.execute_script("arguments[0].click();", pinned_tab)
        
        time.sleep(3) # Wait for tab switch
        print("Successfully clicked 'Pinned' tab.")

        print("Extracting course links...")
        # Now find all enrollment cards
        enrollment_cards = []
        for _ in range(5):
             enrollment_cards = find_all_elements_shadow(driver, 'd2l-enrollment-card')
             if enrollment_cards:
                 break
             time.sleep(1)
             
        if not enrollment_cards:
            print("No enrollment cards found.")
        else:
            print(f"Found {len(enrollment_cards)} visible enrollment cards.")
            
            # Initialize Download Queue
            download_queue = []
            
            # Initialize/Clear the output file
            with open(REPORT_FILE, "w", encoding="utf-8") as f:
                f.write("Brightspace Video Extraction Report\n")
                f.write("===================================\n\n")

            # Helper script to find the course link deep inside the card's shadow DOM
            get_link_script = """
            function getLink(el) {
                function search(root) {
                    if (!root) return null;
                    // Look for the specific anchor tag structure
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
                return search(arguments[0].shadowRoot);
            }
            return getLink(arguments[0]);
            """
            
            unique_links = set()
            for card in enrollment_cards:
                try:
                    # We pass the web element 'card' as an argument to the script
                    href = driver.execute_script(get_link_script, card)
                    if href:
                        if href not in unique_links:
                            unique_links.add(href)
                            print(f"Course Link: {href}")
                    else:
                        # Fallback/Debug if not found
                        # print("Could not find /d2l/home/ link in card.") # Reduce noise
                        pass
                except Exception as ex:
                    print(f"Error extracting link from card: {ex}")

            # Navigation and Module Extraction
            print(f"\nProcessing {len(unique_links)} courses...")
            for course_url in unique_links:
                try:
                    # Transform URL: /d2l/home/123456 -> /d2l/le/content/123456/Home
                    if "/d2l/home/" in course_url:
                        content_url = course_url.replace("/d2l/home/", "/d2l/le/content/") + "/Home"
                    else:
                        print(f"Skipping malformed URL: {course_url}")
                        continue
                        
                    print(f"\nNavigating to Content: {content_url}")
                    driver.get(content_url)
                    time.sleep(5) # Wait for content load

                    # Extract Course Title
                    try:
                        title_elem = driver.find_element(By.CSS_SELECTOR, ".d2l-navigation-s-title-container a")
                        title = title_elem.get_attribute("title")
                        print(f"Course: {title}")
                        
                        # Write Course Header to File
                        with open(REPORT_FILE, "a", encoding="utf-8") as f:
                            f.write(f"\n{'='*50}\n")
                            f.write(f"COURSE: {title}\n")
                            f.write(f"{'='*50}\n")
                    except Exception as e:
                        print(f"Could not extract title: {e}")

                    # Extract Modules and Video Links
                    print("Scanning modules and content...")
                    
                    try:
                        # Wait for tree to be present
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.ID, "D2L_LE_Content_TreeBrowser"))
                        )
                        
                        items = driver.find_elements(By.CSS_SELECTOR, ".d2l-le-TreeAccordionItem-anchor")
                        module_indices = []
                        
                        for i, item in enumerate(items):
                            # Use textContent to get text even if element is hidden/collapsed
                            # We need to be careful with layout text like "module: contains 0 sub-modules" which is hidden
                            # The visible text is usually in a simpler container.
                            # Let's check if the *visible* text contains Module OR if the hidden text implies it's a module we want
                            
                            full_text = item.get_attribute("textContent").strip()
                            if "module" in full_text.lower():
                                # Try to get a cleaner name.
                                # The anchor usually has a child with class 'd2l-textblock' that holds the title.
                                # But we can just clean the textContent.
                                # Usually title is first line.
                                clean_name = full_text.splitlines()[0].strip()
                                if clean_name:
                                    print(f"  Found Module Candidate: {clean_name}")
                                    module_indices.append(i)
                        
                        if not module_indices:
                             print("  No 'Module' items found in tree.")
                        
                        # Path Stack for Hierarchy
                        # Stack stores (level, name) tuples or just names if we track level externally.
                        path_stack = [] 
                        
                        # Open file to append results
                        with open(REPORT_FILE, "a", encoding="utf-8") as f:
                            for index in module_indices:
                                 # Re-acquire items to avoid StaleElementReferenceException
                                 items = driver.find_elements(By.CSS_SELECTOR, ".d2l-le-TreeAccordionItem-anchor")
                                 if index >= len(items):
                                     print(f"  Skipping index {index}: out of range (list changed?)")
                                     continue
                                     
                                 item = items[index]
                                 module_name = item.get_attribute("textContent").strip().splitlines()[0].strip()
                                 
                                 # Determine Hierarchy Level (Name-Based Heuristic)
                                 # Logic: 
                                 # "Module X" -> Root (Level 1)
                                 # "Topic X.Y" -> Child of "Module X" (Level 2)
                                 # Other -> Root (Level 1)
                                 
                                 level = 1
                                 try:
                                     if module_name.startswith("Module ") or module_name.startswith("Module:"):
                                          # Root
                                          path_stack = [module_name]
                                     elif module_name.startswith("Topic "):
                                          # Extract X from Topic X.Y
                                          # e.g. Topic 1.1 -> Parent is Module 1
                                          match = re.search(r"Topic (\d+)\.", module_name)
                                          if match:
                                               parent_num = match.group(1)
                                               # Try to find matching parent in recent history or construct logical name
                                               # We assume parent is "Module {parent_num}..."
                                               # But simple stack logic: if current root starts with "Module {parent_num}", keep it.
                                               if path_stack and path_stack[0].startswith(f"Module {parent_num}"):
                                                    # We are in correct parent
                                                    if len(path_stack) > 1: path_stack.pop() # Remove previous sibling
                                                    path_stack.append(module_name)
                                                    level = 2
                                               else:
                                                    # Parent mismatch or missing? Fail safe to flat.
                                                    # Or reconstruct parent name blindly? BETTER: Just treat as child of whatever is current if it makes sense?
                                                    # Let's try to infer parent name if missing.
                                                    parent_name = f"Module {parent_num}" # Generic fallback
                                                    # Check if we have a better parent name in history? No, too complex.
                                                    # If path_stack has a Module, use it.
                                                    if path_stack and "Module" in path_stack[0]:
                                                         if len(path_stack) > 1: path_stack.pop()
                                                         path_stack.append(module_name)
                                                         level = 2
                                                    else:
                                                         path_stack = [module_name] # Treat as root
                                          else:
                                               path_stack = [module_name]
                                     else:
                                          # "Start Here", "Final", etc.
                                          path_stack = [module_name]
                                     
                                     # Construct relative path
                                     # e.g. "Module 1/Topic 1.1"
                                     safe_path_parts = [sanitize_filename(p) for p in path_stack]
                                     module_path = os.path.join(*safe_path_parts)
                                     
                                     # User requested "videos" subfolder
                                     # We append this to the target_dir construction below, not here in the module path logic
                                     # to keep the module path structure cleaner for logging.
                                     
                                 except Exception as lvl_err:
                                     print(f"    Warning: Name logic failed: {lvl_err}")
                                     module_path = sanitize_filename(module_name)
                                     path_stack = [module_name]

                                 print(f"  \nProcessing: {module_path} (Level {level})")
                                 
                                 # Write Module Header
                                 f.write(f"\n  MODULE: {module_path}\n")
                                 f.write(f"  {'-'*len(module_path)}\n")
                                 
                                 # Click the module to load content
                                 
                                 # Click the module to load content
                                 try:
                                     # Scroll to element to ensure visibility
                                     driver.execute_script("arguments[0].scrollIntoView(true);", item)
                                     time.sleep(1) # Small pause for toggle
                                     # Use JS click for reliability in trees
                                     driver.execute_script("arguments[0].click();", item)
                                 except Exception as click_err:
                                     print(f"    Failed to click module: {click_err}")
                                     continue
                                     
                                 # Wait for content load. 
                                 # We can wait for the 'Active' class on the tree item or just sleep.
                                 time.sleep(5) 
                                 
                                 # Scrape Video Links
                                 try:
                                     video_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/viewContent/']")
                                     unique_vids = set()
                                     for vid in video_links:
                                         v_href = vid.get_attribute("href")
                                         v_text = vid.text.strip()
                                         v_title_attr = vid.get_attribute("title") or ""
                                         
                                         if not v_text:
                                             # Fallback to title attribute if text is empty
                                             if v_title_attr:
                                                 # Remove " - External Learning Tool" suffix if present
                                                 v_text = v_title_attr.replace(" - External Learning Tool", "").replace("'", "").strip()
                                         
                                         # Content Classification Logic
                                         timestamp_pattern = re.compile(r'\(\d+:\d+\)')
                                         
                                         tag = "[OTHER]"
                                         # Broadened PDF detection
                                         v_text_lower = v_text.lower()
                                         v_title_lower = v_title_attr.lower()
                                         
                                         if "pdf" in v_text_lower or "pdf" in v_title_lower:
                                             tag = "[PDF]"
                                         elif "slides" in v_text_lower or "slides" in v_title_lower:
                                              tag = "[PDF]" # Assume slides are PDFs
                                         elif "external learning tool" in v_title_lower:
                                              tag = "[VIDEO]" # Likely a video/Kaltura
                                         elif timestamp_pattern.search(v_text):
                                              tag = "[VIDEO]"
                                         elif "quiz" in v_text.lower():
                                              tag = "[QUIZ]"
                                         
                                         if v_href and v_href not in unique_vids:
                                             unique_vids.add(v_href)
                                             print(f"    {tag} {v_text}")
                                             f.write(f"    - {tag} {v_text}\n") # Save to file with indent
                                             
                                             # Trigger Queueing
                                             should_queue = False
                                             content_type = "video" # default

                                             if tag == "[VIDEO]":
                                                 should_queue = True
                                                 content_type = "video"
                                             elif tag == "[PDF]" and DOWNLOAD_PDFS:
                                                 print(f"      [QUEUE] Adding PDF to download queue: {v_text}")
                                                 should_queue = True
                                                 content_type = "pdf"
                                             
                                             if should_queue:
                                                 if tag == "[VIDEO]":
                                                     print(f"      [QUEUE] Adding video to download queue: {v_text}")

                                                 try:
                                                     # safe names
                                                     safe_course = sanitize_filename(title)
                                                     # module_path is already sanitized and hierarchical (e.g. "Mod 1/Topic 1")
                                                     
                                                     # Determine subfolder based on type
                                                     subfolder = "videos"
                                                     if content_type == "pdf":
                                                         subfolder = "pdfs" # separate folder for PDFs? or mixed?
                                                         # User said "save the PDFs in the class as well". 
                                                         # "That way we can download both PDFs and videos"
                                                         # In the prototype, user had: class_folder/Modules/module_name/Content Videos/ or Readings/
                                                         # Here we have generic output structure: downloads/course/module_path/videos
                                                         # I should probably just change "videos" to "content" or have specific folders?
                                                         # Current code hardcodes "videos".
                                                         # Let's use "pdfs" for PDFs and "videos" for videos to keep them organized, 
                                                         # or user might prefer them together? 
                                                         # User's prototype has: 
                                                         # content_videos_folder = os.path.join(module_folder, "Content Videos")
                                                         # readings_folder = os.path.join(module_folder, "Readings")
                                                         # syllabus.pdf went to class_folder root.
                                                         # Let's put PDFs in a 'pdfs' folder alongside 'videos' folder.
                                                     
                                                     target_dir = os.path.join(DOWNLOADS_DIR, safe_course, module_path, subfolder)
                                                     
                                                     download_queue.append({
                                                         "title": v_text,
                                                         "url": v_href,
                                                         "target_dir": target_dir,
                                                         "type": content_type
                                                     })
                                                     
                                                 except Exception as q_ex:
                                                     print(f"      [ERROR] Queueing failed: {q_ex}")

                                 except Exception as vid_err:
                                     print(f"    Error finding videos: {vid_err}")

                    except Exception as e:
                        print(f"  Error extracting modules/content: {e}")

                except Exception as e:
                    print(f"Error processing course {course_url}: {e}")

            # Deduplicate Queue (Keep Deepest Path, then First Found)
            # Strategy: 
            # 1. Prefer deeper hierarchy (e.g. "Module 1/Topic 1" > "Module 1")
            # 2. If depth is equal, keep the FIRST one found (Preserve "Week X" over "Assessments" if Week X comes first)
            
            unique_queue_map = {}
            for item in download_queue:
                url = item['url']
                target_dir = item['target_dir']
                
                # Calculate depth by counting separators
                # usage of os.sep matters
                depth = target_dir.count(os.sep)
                
                if url in unique_queue_map:
                    current_depth = unique_queue_map[url]['depth']
                    
                    if depth > current_depth:
                         # Found a deeper path, replace
                         unique_queue_map[url] = {**item, 'depth': depth}
                    # Else: keep existing (first wins)
                else:
                    unique_queue_map[url] = {**item, 'depth': depth}
            
            # Remove the 'depth' helper key before saving
            final_queue = []
            for item in unique_queue_map.values():
                clean_item = {k: v for k, v in item.items() if k != 'depth'}
                final_queue.append(clean_item)
            
            print(f"\nSaving {len(final_queue)} unique items to {QUEUE_FILE} (Filtered from {len(download_queue)}) ...")
            with open(QUEUE_FILE, "w", encoding="utf-8") as f:
                json.dump(final_queue, f, indent=2)
            print("Queue saved.")

    except Exception as e:
        print(f"An error occurred: {e}")
        driver.save_screenshot("error_screenshot.png")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
