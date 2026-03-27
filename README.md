# Pancake Daily Customer Follow-up

> 🇻🇳 **[Đọc bản tiếng Việt tại đây (Vietnamese)](README.vi.md)**

Community-ready reference project for daily follow-up of **silent Pancake conversations** using a hybrid approach:
- **Pancake API** to scan eligible conversations
- **Playwright + Chromium CDP** to open the real Pancake UI and send follow-up messages conservatively

This repository is designed to be **shareable on GitHub**:
- no real tokens included
- no private page IDs or profile paths required in source code
- no runtime customer data committed
- all sensitive values are provided by the user through environment variables

> ## Important
> This repository is a **reference implementation**, not a turnkey growth tool.
> Before using it in production, you should review:
> - Pancake terms of service
> - Facebook / Meta platform policies
> - local privacy, consent, and customer-contact regulations
> - your own operational approval process
>
> You are responsible for how you configure, review, and use this workflow.

## What this project does

Each run can:
1. scan conversations from a Pancake page
2. filter customers who have been silent for `N` days
3. exclude conversations with blocked tags such as `ĐÃ CHỐT` or `KHÔNG MUA`
4. deduplicate by customer Facebook ID
5. attach to a logged-in Chromium session via CDP
6. search the customer inside Pancake UI
7. skip comment threads and send only when the script can verify a real Messenger conversation
8. save run results, queue state, and anti-duplicate state to local JSON files

## Business rule used by default

A conversation is eligible when:
- the last sender is the page/admin
- the conversation is older than `PANCAKE_SCAN_DAYS` (default `2`)
- tags do **not** contain `ĐÃ CHỐT`
- tags do **not** contain `KHÔNG MUA`

## Safety behavior

This workflow is intentionally conservative:
- if the UI looks like a **comment thread**, it skips
- if the search result cannot be verified confidently, it skips
- if the message already exists in the thread, it skips
- if a customer was already sent in a previous run, it skips

Goal: **fail safe instead of sending to the wrong conversation**.

---

## Project structure

```text
pancake-daily-customer-followup-community/
├─ README.md
├─ LICENSE
├─ requirements.txt
├─ .gitignore
├─ config/
│  └─ .env.example
├─ data/
│  └─ .gitkeep
├─ docs/
│  └─ sample-scan-output.json
├─ scripts/
│  ├─ run_followup.sh
│  └─ smoke_test.sh
└─ src/
   └─ pancake_followup.py
```

---

## Requirements

- macOS or Linux
- Python 3.10+
- Chromium installed
- a Pancake page account already logged in inside the chosen Chromium profile
- permission to access Pancake API for your page

## Required user-provided information

Before running, the user must provide:

### Pancake API
- `PANCAKE_PAGE_ID`
- `PANCAKE_PAGE_ACCESS_TOKEN`
- `PANCAKE_PAGE_KEY` (friendly name, for example `my-page`)
- `PANCAKE_PAGE_URL` (for example `https://pancake.vn/my-page-slug`)

### Browser / UI automation
- a Chromium installation path
- a Chromium user profile path that is already logged into Pancake
- a CDP port / CDP URL

### Optional business config
- follow-up message template
- maximum sends per run
- silent-day threshold
- output file locations

---

## Setup

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd pancake-daily-customer-followup-community
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

### 3. Create your `.env`

```bash
cp config/.env.example .env
```

Then fill in the real values.

Example:

```env
PANCAKE_PAGE_KEY=my-page
PANCAKE_PAGE_ID=YOUR_PAGE_ID
PANCAKE_PAGE_ACCESS_TOKEN=YOUR_PAGE_ACCESS_TOKEN
PANCAKE_PAGE_URL=https://pancake.vn/YOUR_PAGE_SLUG

PANCAKE_API_BASE=https://pages.fm/api/public_api
PANCAKE_SCAN_DAYS=2
PANCAKE_LOOKBACK_DAYS=14
PANCAKE_SCAN_LIMIT=100
PANCAKE_MAX_SEND_PER_RUN=5
PANCAKE_MESSAGE_TEMPLATE=Hi anh/chị, em follow up lại cuộc trao đổi trước. Nếu anh/chị vẫn còn quan tâm, em có thể gửi thêm thông tin chi tiết để mình tham khảo nhanh ạ.

PANCAKE_CHROMIUM_PROFILE=$HOME/Library/Application Support/pancake-community-followup
PANCAKE_CHROMIUM_CDP_PORT=9239
PANCAKE_CHROMIUM_CDP_URL=http://127.0.0.1:9239
PANCAKE_CHROMIUM_APP=/Applications/Chromium.app
PANCAKE_CHROMIUM_BIN=/Applications/Chromium.app/Contents/MacOS/Chromium
PANCAKE_PYTHON_BIN=python3
```

### 4. Log into Pancake in Chromium

Use the same Chromium profile you configured in `.env`.

If Chromium is not already running with remote debugging, the runner script will try to start it.

---

## Usage

### A. Scan only

```bash
set -a && source .env && set +a
python src/pancake_followup.py scan
```

This prints a JSON result with:
- total raw conversations
- excluded counts by rule
- eligible candidates

A sample sanitized output is included at:
- `docs/sample-scan-output.json`

### B. Run the daily follow-up sender

```bash
chmod +x scripts/run_followup.sh
./scripts/run_followup.sh
```

This will:
1. ensure Chromium CDP is available
2. scan candidates
3. build a send queue
4. attach to Pancake UI
5. send up to `PANCAKE_MAX_SEND_PER_RUN`
6. save results to JSON files

### C. Run a local smoke test

```bash
chmod +x scripts/smoke_test.sh
./scripts/smoke_test.sh
```

This validates:
- Python syntax for the main script
- required documentation files exist
- `.env.example` contains placeholder-only values
- no obvious local runtime JSON files are tracked in `data/`

---

## Output files

By default the script writes:

- `data/pancake-followup-state.json`  
  anti-duplicate memory, pending locks, send history

- `data/pancake-followup-queue.json`  
  queue generated for the current run

- `data/pancake-followup-last-run.json`  
  final run summary, sent list, failed list, skipped list

---

## Why CDP + real Chromium?

Many Pancake workflows are more stable when attached to a real logged-in browser session instead of trying to log in from scratch in a fresh headless browser every time.

Benefits:
- reuse a persistent logged-in session
- easier debugging
- closer to real operator workflow
- safer UI validation before sending

---

## Why some candidates fail

Typical failure reasons:
- `comment_ui_detected_skip`
- `no_messenger_candidate_after_search`
- `conversation_search_input_not_found`
- `post_send_message_not_detected_message`

These are expected safe-fail outcomes in ambiguous UI cases.

---

## Recommended production workflow

1. test with `scan` only
2. verify a few candidate conversations manually in Pancake UI
3. set `PANCAKE_MAX_SEND_PER_RUN=1` for first send tests
4. increase gradually after confidence improves
5. keep logs and result files for audit
6. review whether your message content and contact cadence are compliant for your market/use case

---

## Security and privacy notes

Do **not** commit the following:
- `.env`
- real Pancake access tokens
- real page IDs if you consider them private
- real customer data JSON outputs
- private browser profiles
- screenshots or logs containing customer names/messages

This repository already ignores common sensitive runtime files through `.gitignore`, but you should still review local changes before pushing.

---

## Cron example

Run every day at 13:00:

```cron
0 13 * * * cd /path/to/pancake-daily-customer-followup-community && /bin/bash scripts/run_followup.sh >> /tmp/pancake-followup-cron.log 2>&1
```

---

## Customization ideas

You can extend this project with:
- Telegram approval before send
- multi-page support
- configurable excluded tags
- screenshot capture for failed cases
- CSV/Google Sheets export
- retry and backoff policies
- Slack/Discord notifications

---

## Disclaimer

Use responsibly and comply with:
- Pancake terms
- Facebook platform policies
- local privacy and customer-contact regulations

Review the message template, business rules, and approval process before enabling automated sends.

---

## License

MIT
