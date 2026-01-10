# Extract Kaltura Videos from Brightspace

## Goal
Download video content from specific Brightspace video URLs using the `kaltura_video_extractor.py` script.

## Prerequisites
- Python installed
- Chrome browser installed
- Valid Brightspace session cookies configured in `.env/.env`
- Dependencies: `selenium`, `undetected-chromedriver`, `selenium-wire`, `requests`, `python-dotenv`

## Inputs
- `execution/kaltura_video_extractor.py`: The extraction script.
- `.env/.env`: Configuration file containing session cookies.
- Target Brightspace Video Page URLs.

## Configuration

1.  **Obtain Session Cookies**:
    - Log in to Purdue Brightspace in Chrome.
    - Open Developer Tools (F12) -> Application tab -> Cookies -> `https://purdue.brightspace.com`.
    - Retrieve values for: `d2lSecureSessionVal`, `d2lSessionVal`.

2.  **Setup Environment Variables**:
    - Edit the file `.env/.env` (create it if it doesn't exist).
    - Add the following lines, replacing the values with your actual cookies:
      ```env
      D2L_SECURE_SESSION_VAL=your_value
      D2L_SESSION_VAL=your_value
      ```

## Execution

1.  **Run the Extractor**:
    - Open a terminal in the project root.
    - Run the script with the desired URLs and output directory:
      ```bash
      python execution/kaltura_video_extractor.py --urls "https://purdue.brightspace.com/..." "https://purdue.brightspace.com/..." --output-dir "my_videos"
      ```
    - You can pass as many URLs as needed.

## Verify Output
- Check the specified output directory.
- Videos should be saved there as `.mp4` files.

## Troubleshooting
- **Cookies Expired**: If the script fails or returns 401/403, update the values in `.env/.env`.
- **Missing .env**: Ensure `.env/.env` exists and contains all required keys.
