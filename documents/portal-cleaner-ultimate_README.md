# Portal Cleaner Ultimate

Portal Cleaner Ultimate is a Tkinter and Selenium based desktop tool for scanning work orders in an ERP portal, filtering them by date, status, or product-code file, and then processing the matching rows automatically.

The codebase was refactored into smaller modules to make the project easier to read, test, and maintain.

## Project Structure

- `app.py` - Tkinter UI and main application flow
- `config.py` - Central configuration values
- `filters.py` - Date and row filtering logic
- `io_utils.py` - File readers and error logging
- `webdriver_manager.py` - Selenium browser and page automation
- `run_full_flow.py` - Command-line end-to-end runner for the mock flow
- `debug_fetch.py` - Small Selenium debugging helper
- `mock_site/` - Local HTML pages used for offline testing

## Features

- Date-based filtering with `dd.mm.yyyy` input
- Status-based filtering for rows such as `HAZIRLIK`
- Product-code file support for `.txt`, `.xlsx`, `.xls`, and `.xml`
- Selenium automation for opening and processing matching work orders
- Centralized error logging to `error_urunler.txt`
- Local mock site for testing without ERP access

## Requirements

- Python 3
- Google Chrome
- A matching ChromeDriver accessible to Selenium
- Python packages from `requirements.txt`

## Installation

Create or activate the project virtual environment, then install dependencies:

```bash
pip install -r requirements.txt
```

## Run the GUI

Start the desktop app with:

```bash
python app.py
```

The GUI lets you enable filters, pick a product-code file, and start processing from the same window.

## Run the Local Mock Test

The project currently points to the local mock site so the flow can be tested without access to the real ERP portal.

Start a simple server from the project root:

```bash
python -m http.server 8000
```

Then run the full flow in another terminal:

```bash
python run_full_flow.py
```

The mock product page shows visible feedback when buttons are clicked, so you can confirm that Selenium is actually interacting with the page.

## Production Mode

By default, the application uses the local mock site.

To switch to a real ERP environment, start the app or the CLI runner with `--prod` and provide the URLs through environment variables:

```bash
set PORTAL_CLEANER_PROD=1
set PORTAL_CLEANER_START_URL=https://your-erp.example.com/index.html
set PORTAL_CLEANER_BASE_URL=https://your-erp.example.com/
python app.py --prod
```

You can also use `PORTAL_CLEANER_MODE=prod` instead of `PORTAL_CLEANER_PROD=1`.

If you only set `PORTAL_CLEANER_START_URL`, the base URL is inferred automatically.

## How the Flow Works

1. The app loads the configured start page.
2. It reads the table rows and applies the selected filters.
3. Matching rows are opened and processed with Selenium.
4. Failed rows and error pages are logged to `error_urunler.txt`.
5. The UI log shows the current progress and final result.

## Configuration

The active URL is set in `config.py`.

- For local testing, `START_URL` points to `http://localhost:8000/mock_site/index.html`
- For production use, pass `--prod` and set `PORTAL_CLEANER_START_URL` or `PORTAL_CLEANER_BASE_URL`

Other useful settings in `config.py`:

- Wait and delay values
- Retry count
- Error keywords used to detect failure pages
- Error log file name

## Input Files

Product code files can be loaded in these formats:

- `.txt`
- `.xlsx`
- `.xls`
- `.xml`

## Troubleshooting

- If the browser opens and closes too early, make sure you are using the project virtual environment and that Chrome is installed.
- If Selenium cannot find rows, confirm that the mock server is running on port 8000.
- If the real ERP portal is not reachable from this machine, use the mock flow above to verify the application end to end.

## Notes

- The mock site is intentionally simple and is only for local testing.
- If you want to switch back to production, update the URLs in `config.py` before running the GUI.
