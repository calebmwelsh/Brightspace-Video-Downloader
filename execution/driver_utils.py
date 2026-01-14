import os
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

def setup_driver(headless=False):
    """Sets up and returns a Selenium Wire driver with undetected-chromedriver options."""
    chrome_options = uc.ChromeOptions()
    chrome_options.add_argument(f"--user-agent={USER_AGENT}")
    if headless:
         chrome_options.add_argument("--headless")
    
    # Use seleniumwire's webdriver.Chrome, but with undetected_chromedriver's options
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_window_size(1728, 1080)
    return driver

def load_brightspace_cookies(driver):
    """Loads Brightspace cookies from .env/.env and adds them to the driver."""
    dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env', '.env')
    load_dotenv(dotenv_path=dotenv_path, override=True)

    cookies = [
        {"name": "d2lSameSiteCanaryA", "value": "1", "domain": ".purdue.brightspace.com"},
        {"name": "d2lSameSiteCanaryB", "value": "1", "domain": ".purdue.brightspace.com"},
        {"name": "d2lSecureSessionVal", "value": os.getenv("D2L_SECURE_SESSION_VAL"), "domain": ".purdue.brightspace.com"},
        {"name": "d2lSessionVal", "value": os.getenv("D2L_SESSION_VAL"), "domain": ".purdue.brightspace.com"},
    ]
    
    # Check if critical cookies are present
    # We used to exit here, but now we want to fallback to auto-login.
    # So we just warn and proceed. validate_and_refresh_session will handle the login page redirect.
    if not all(c["value"] for c in cookies if c["name"] in ["d2lSecureSessionVal", "d2lSessionVal"]):
        print("Warning: Missing cookies in .env. Will attempt auto-login shortly.")
    else:
        print("Cookies loaded from .env.")

    driver.get("https://purdue.brightspace.com")  # Must be on domain before adding cookies
    for cookie in cookies:
        if cookie["value"]: # Only add if value exists
             driver.add_cookie(cookie)
    
    # Reload the page to apply cookies and clear any login redirects
    driver.get("https://purdue.brightspace.com")




def save_cookies_to_env(cookies_dict):
    """Updates the .env/.env file with new cookie values."""
    dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env', '.env')
    
    # Read existing content
    with open(dotenv_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    new_lines = []
    for line in lines:
        if line.startswith("D2L_SECURE_SESSION_VAL="):
            new_lines.append(f"D2L_SECURE_SESSION_VAL={cookies_dict.get('d2lSecureSessionVal', '')}\n")
        elif line.startswith("D2L_SESSION_VAL="):
            new_lines.append(f"D2L_SESSION_VAL={cookies_dict.get('d2lSessionVal', '')}\n")
        else:
            new_lines.append(line)
            
    with open(dotenv_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print("Updated .env with fresh cookies.")

def find_element_shadow(driver, selector):
    """
    Finds an element using a CSS selector, traversing through open Shadow DOM roots.
    """
    script = f"""
    function findElement(selector, root = document) {{
        // Check current root
        let element = root.querySelector(selector);
        if (element) return element;
        
        // Check all children with shadowRoots
        let elements = root.querySelectorAll('*');
        for (let el of elements) {{
            if (el.shadowRoot) {{
                let found = findElement(selector, el.shadowRoot);
                if (found) return found;
            }}
        }}
        return null;
    }}
    return findElement(arguments[0]);
    """
    return driver.execute_script(script, selector)

def perform_purl_login(driver):
    """Performs the login sequence via Purdue authentication."""
    print("Attempting Auto-Login...")
    print(f"Current URL before login attempt: {driver.current_url}")
    
    try:
        # 1. Click "Purdue West Lafayette / Indianapolis"
        login_link = None
        
        # Try standard find first
        try:
             login_link = WebDriverWait(driver, 5).until(
                 EC.element_to_be_clickable((By.CSS_SELECTOR, "a[title*='Purdue West Lafayette']"))
             )
        except:
             pass
             
        # Try Shadow DOM find if standard failed
        if not login_link:
            print("Standard search failed. Trying Shadow DOM search for 'Purdue West Lafayette'...")
            login_link = find_element_shadow(driver, "a[title*='Purdue West Lafayette']")
            
        # Fallback to generic IDP if specific title fails
        if not login_link:
             print("Specific title not found. Trying generic IDP link in Shadow DOM...")
             # Note: This might pick up Fort Wayne or Northwest if they share the IDP, but usually specific is better.
             # Purdue West Lafayette usually has 'idp.purdue.edu' while others might have different ones?
             # User snippet shows others have different entityIds (e.g. pfw, purdueglobal).
             # West Lafayette is 'https://idp.purdue.edu/idp/shibboleth'
             login_link = find_element_shadow(driver, "a[href*='idp.purdue.edu']")

        if login_link:
             print("Found Login Link. Clicking...")
             # Use JS click to be safe with Shadow DOM elements
             driver.execute_script("arguments[0].click();", login_link)
        else:
             print("Login link not found. Assuming we might already be at the form...")

        # 2. Login Form
        print(f"Waiting for Login Form (URL: {driver.current_url})...")
        
        # Wait for username field
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "username"))
        )
         
        username = os.getenv("D2L_USERNAME")
        password = os.getenv("D2L_PASSWORD")
        
        if not username or not password:
            print("Error: D2L_USERNAME or D2L_PASSWORD not set in .env")
            return False

        print("Entering credentials...")
        driver.find_element(By.ID, "username").send_keys(username)
        driver.find_element(By.ID, "password").send_keys(password)
        
        submit_btn = driver.find_element(By.NAME, "_eventId_proceed")
        submit_btn.click()
        print("Submitted credentials.")
        
        # 3. 2FA / Session Wait
        print("Waiting for login to complete (Check for 2FA on your device if needed)...")
        
        # Wait for redirect back to brightspace
        WebDriverWait(driver, 120).until( # Increased wait time for 2FA
            EC.url_contains("purdue.brightspace.com/d2l/home")
        )
        print("Login successful! Session established.")
        return True
        
    except Exception as e:
        print(f"Login failed: {e}")
        # Print page source snippet to debug
        try:
            print(f"Page Source Preview: {driver.page_source[:500]}")
        except: pass
        return False

def validate_and_refresh_session(driver):
    """
    Checks if session is valid. If not, restarts driver in NON-HEADLESS mode,
    performs login, updates cookies, and returns the new driver.
    """
    # Check if we are on a login page or home page
    # If we just loaded cookies and refreshed, we should be on /d2l/home
    current_url = driver.current_url
    if "login" in current_url.lower() or "auth" in current_url.lower():
        print("Session appears expired (Redirected to Login).")
        
        # We need to switch to Headless=False to allow potential interactivity (2FA)
        # and just to be safe.
        print("Relaunching driver in NON-HEADLESS mode for authentication...")
        driver.quit()
        
        driver = setup_driver(headless=False)
        driver.get("https://purdue.brightspace.com")
        
        if perform_purl_login(driver):
            # Capture new cookies
            new_cookies = {}
            for c in driver.get_cookies():
                if c['name'] in ['d2lSecureSessionVal', 'd2lSessionVal']:
                    new_cookies[c['name']] = c['value']
            
            if new_cookies:
                save_cookies_to_env(new_cookies)
                
                # Switch back to HEADLESS mode for the rest of the run
                print("Login verified. Switching back to HEADLESS mode...")
                driver.quit()
                driver = setup_driver(headless=True)
                load_brightspace_cookies(driver) # Reloads the fresh cookies from .env
                print("Reloading Homepage with new session...")
                driver.get("https://purdue.brightspace.com") # Apply cookies by navigating
            
            else:
                print("Warning: Could not capture new cookies after login.")
        else:
            print("Auto-login failed. Please login manually in the window.")
            # We could pause here?
            input("Press Enter after you have manually logged in and are on the Brightspace homepage >> ")
            # Capture anyway
            new_cookies = {}
            for c in driver.get_cookies():
                if c['name'] in ['d2lSecureSessionVal', 'd2lSessionVal']:
                    new_cookies[c['name']] = c['value']
            save_cookies_to_env(new_cookies)
            
            # Even after manual login, we should probably switch back to headless?
            # Users might prefer to keep it verification, but for consistency lets switch back if successful.
            if new_cookies:
                 print("Manual login verified. Switching back to HEADLESS mode...")
                 driver.quit()
                 driver = setup_driver(headless=True)
                 load_brightspace_cookies(driver)
            
    return driver
