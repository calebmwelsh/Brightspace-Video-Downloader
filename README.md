# Brightspace Content Extractor

A robust, agentic workflow for scraping and downloading video content (specifically Kaltura/Brightspace videos) from Purdue University's Brightspace learning management system.

## 🚀 Features

- **Automated Authentication**: Handles login flows, including 2FA waits and session cookie extraction.
- **Shadow DOM Traversal**: Advanced element detection to navigate complex web components used in Brightspace.
- **Batch Processing**:
    1.  **Parser**: Scans "Pinned" courses, navigates modules, and builds a download queue.
    2.  **Downloader**: Processes the queue in headless mode to download video streams.
- **Resilient**: Handles network retries, session refreshing, and "Headless" browser detection avoidance.

## 🛠️ Architecture

This project follows a **3-Layer Architecture** to separate intent from execution:

1.  **Directives (`directives/`)**: Markdown-based Standard Operating Procedures (SOPs) that define *what* to do.
2.  **Orchestration (Agent)**: The AI agent (or human) reads directives and calls the tools.
3.  **Execution (`execution/`)**: Deterministic Python scripts that perform the actual work.

## 📋 Prerequisites

- **Windows OS** (Primary support)
- **Python 3.10+**
- **Google Chrome** (Latest version)

### Dependencies
Install the required Python packages:

```bash
pip install selenium undetected-chromedriver selenium-wire requests python-dotenv
```

## ⚙️ Configuration

1.  **Environment Variables**:
    Copy the example file to the expected location:
    
    ```bash
    # Windows
    copy .env\.env.example .env\.env

    # Linux/Mac
    cp .env/.env.example .env/.env
    ```
    
    Then open `.env/.env` and fill in your values (optional, as the parser can auto-login and fill this for you).

    ```env
    D2L_SECURE_SESSION_VAL=...
    D2L_SESSION_VAL=...
    
    # Optional: Auto-login
    D2L_USERNAME=...
    D2L_PASSWORD=...
    ```

    *Note: The `brightspace_parser.py` script can automatically populate the **session cookies** (`D2L_..._VAL`) in this file after a successful login. It does **not** save your username or password.*

## ▶️ Usage

### Step 1: content Discovery
Run the parser to scan your "Pinned" courses and identify video content.

```bash
python execution/brightspace_parser.py
```

- **Action**: Opens a browser (if login needed), scans courses, and generates a queue.
- **Output**: 
    - `download_queue.json`: List of videos to download.
    - `video_titles.txt`: A readable report of found content.

### Step 2: Batch Download
Download the videos found in the previous step.

```bash
python execution/batch_downloader.py
```

- **Action**: Runs in headless mode (default) to download videos.
- **Output**: Videos saved to `downloads/{Course Name}/{Module Name}/`.

## 📂 Project Structure

```
.
├── directives/             # SOPs / Instructions
│   ├── parse_brightspace.md
│   └── run_extraction_pipeline.md
├── execution/              # Python scripts
│   ├── brightspace_parser.py
│   ├── batch_downloader.py
│   └── driver_utils.py
├── .env/                   # Secrets (GitIgnored)
└── AGENTS.md               # System instructions
```

## ⚠️ Disclaimer
> [!WARNING]
> **DISCLAIMER: EDUCATIONAL USE ONLY**
> 
> This tool is strictly for **educational and personal archiving purposes**. 
> - **Do not use** this tool to distribute copyrighted material.
> - **Ensure compliance** with your institution's Acceptable Use Policy (AUP) and relevant copyright laws.
> - The authors assume **no liability** for misuse of this software.
