# Parse Brightspace

## Goal
Authenticate into Brightspace and navigate to the "Pinned" courses tab. This is a foundational script for further parsing.

## Prerequisites
- Python installed
- Chrome browser installed
- Valid Brightspace session cookies in `.env/.env`

## Inputs
- `execution/brightspace_parser.py`
- `.env/.env` configuration

## Instructions

1.  **Run the Parser**:
    - Open a terminal in the project root.
    - Run the script:
      ```bash
      python execution/brightspace_parser.py
      ```
    - **Note on Login**: If your cookies are expired or missing, the script will automatically launch a visible browser window, log in on your behalf, and wait for you to approve 2FA. Once confirmed, it will scrape new cookies, update your `.env` file, and resume automatically in headless mode.

3.  **Expected Output**:
    - The script will launch a browser, handle authentication if needed, and navigate to the "Pinned" tab.
    - Console output should confirm "Successfully selected 'Pinned' tab."

## Troubleshooting
- **Element Not Found**: Check if the page layout has changed.
- **Auto-Login Stuck**: If the browser opens but doesn't log in, manually enter your credentials and press Log In. The script will still capture the cookies once you reach the homepage.
