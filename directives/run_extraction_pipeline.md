# Run Extraction Pipeline

This pipeline extracts video content from Brightspace courses and downloads them.

## Prerequisites
1.  **Cookies**: Ensure `.env/.env` is updated with valid `d2lSecureSessionVal` and `d2lSessionVal` cookies.

## Workflow

### Step 1: Crawl and Queue
Run the parser to scan courses and build a download queue. This step does **not** download files, so it is fast.
```bash
python execution/brightspace_parser.py
```
*   **Output**: `download_queue.json`
*   **Report**: `video_titles.txt`

### Step 2: Batch Download
Run the downloader to process the queue in headless mode.
```bash
python execution/batch_downloader.py
```
*   **Output**: Videos in `downloads/{Course Name}/{Module Name}/`
*   **Logs**: Console output shows progress.

## Troubleshooting
*   **"No content found"**: Check likely cookie expiration. Update `.env`.
*   **"Headless crash"**: Try running `batch_downloader.py` with `setup_driver(headless=False)` for debugging.
