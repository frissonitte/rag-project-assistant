# listing-pilot

> Appium-powered seller automation for Turkish second-hand marketplaces.

Built out of a real need: managing ~1000 active listings across [Dolap](https://dolap.com) and [Gardrops](https://gardrops.com) by hand was eating hours every week. This bot handles the repetitive parts — bulk price updates, listing refreshes, and description fixes — so the only thing left to do manually is actually selling.

---

## What it does

The bot connects to a running Android emulator via Appium and navigates the marketplace app on your behalf, operating entirely within your own seller account.

**Price operations** (applied to all listings in a single pass):

| Mode      | Description                                                                |
| --------- | -------------------------------------------------------------------------- |
| Drop      | Decrease every price by a fixed amount (e.g. −1 TL)                        |
| Fix       | Snap prices up to the next defined price tier (80 → 120 → 160 → 200 → 249) |
| Increment | Raise every price by a fixed amount; capped at 249 TL for sub-249 listings |

**Listing operations:**

| Mode               | Description                                                                         |
| ------------------ | ----------------------------------------------------------------------------------- |
| Refresh            | Re-submits every listing for approval, pushing it back to the top of search results |
| Description update | Find-and-replace a substring across all listing descriptions in one run             |

---

## Architecture

```
runner script              dolap_core.py             automation_targets.private.json
(dolap_price_drop.py)  →  run_marketplace_bot()  →  Appium capabilities + UI selectors
```

Appium capabilities and all UI element selectors live in `automation_targets.private.json` (gitignored). The core loop in `dolap_core.py` is selector-agnostic — swapping in a different marketplace requires only a new profile entry in the config file, not changes to the bot logic.

Gardrops has its own standalone script (`gardrops_price.py`) with a simpler architecture, since it covers only price updates and its UI differs significantly.

Optional Telegram alerts notify you on completion or when the bot encounters an unrecoverable error.

---

## Requirements

- Python 3.11+
- [Appium Server](https://appium.io) 2.x with the `uiautomator2` driver
- Android emulator (tested on AVD with API 33) **already logged into your seller account**
- The marketplace app installed on the emulator

Install Python dependencies:

```bash
pip install -r requirements.txt
```

<details>
<summary>requirements.txt</summary>

```
appium-python-client
selenium
python-dotenv
requests
```

</details>

---

## Setup

**1. Configure selectors**

Copy the example config and fill in your app's resource IDs:

```bash
cp automation_targets.example.json automation_targets.private.json
```

Windows PowerShell:

```powershell
Copy-Item automation_targets.example.json automation_targets.private.json
```

The example file documents every field. Resource IDs can be found with [uiautomatorviewer](https://developer.android.com/training/testing/other-components/ui-automator) or Appium Inspector.

**2. Set up environment variables**

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Fill in `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` if you want completion alerts. Leave both blank to disable.

**3. Start Appium**

```bash
appium
```

**4. Start your emulator and open the marketplace app**, then navigate to your product list screen (Gardrops only — Dolap navigates automatically).

---

## Usage

Each runner script configures `MarketplaceBotConfig` for a specific task and calls the shared core loop.

```bash
# Drop every listing price by 1 TL
python dolap_price_drop.py

# Snap prices to the nearest tier (80/120/160/200/249)
python dolap_price_fix.py

# Raise every price by 9 TL (capped at 249 for sub-249 listings)
python dolap_price_increment.py

# Re-submit all listings for approval (refreshes search position)
python dolap_description_change.py

# Gardrops price update (map / drop / increment — set MODE in script)
python gardrops_price.py
```

To customise a run, edit the `MarketplaceBotConfig` fields at the top of the relevant runner script. All fields are documented in `dolap_core.py`.

---

## Project structure

```
listing-pilot/
├── dolap_core.py                      # Core bot engine and all shared helpers
├── dolap_price_drop.py                # Runner: price drop
├── dolap_price_fix.py                 # Runner: price tier snap
├── dolap_price_increment.py           # Runner: price increment
├── dolap_description_change.py        # Runner: description update + listing refresh
├── gardrops_price.py                  # Standalone Gardrops price bot
├── target_profiles.py                 # Loads automation_targets.private.json
├── automation_targets.example.json    # Config template (commit this)
├── automation_targets.private.json    # Your actual selectors (gitignored)
├── .env.example
└── .gitignore
```

---

## Notes

- The bot operates on your own seller account using your own credentials. It does not scrape other users' listings or access any non-public data.
- `no_reset: true` is set by default — the emulator session is reused across runs, so you stay logged in.
- Edit button coordinates (`edit_button_x`, `edit_button_y`) in `MarketplaceBotConfig` are screen-resolution-specific. If taps land in the wrong place, inspect your emulator's resolution and adjust accordingly.
- The Gardrops bot requires manual navigation to the product list before the 5-second countdown completes.

---

## License

MIT
