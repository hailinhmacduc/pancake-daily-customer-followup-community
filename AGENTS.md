# AGENTS.md

Agent-facing setup and operating guide for **Pancake Daily Customer Follow-up**.

This file is written for AI coding agents and technical assistants that receive a link to this repository and need to help a user install, configure, test, and operate it safely.

---

## 1) What this project is

This repository is a **reference implementation** for following up with silent Pancake conversations using:
- **Pancake API** for scanning/filtering candidate conversations
- **Playwright + Chromium CDP** for opening the real Pancake UI and sending follow-up messages conservatively

It is **not** a zero-review autopilot sender.

Primary design goal:
- **fail safe rather than send to the wrong conversation**

---

## 2) What an agent should understand before helping the user

This project has two very different phases:

### A. Scan phase
Safe, read-heavy workflow:
- call Pancake API
- list eligible conversations
- apply filters
- produce JSON output

### B. Send phase
More sensitive workflow:
- attach to a **real logged-in Chromium session**
- open the Pancake UI
- search/select conversation candidates
- send follow-up messages if UI validation passes

Because the send phase can contact real customers, agents should treat it as a **high-caution action**.

---

## 3) What the agent may do automatically

An agent may usually do these steps without needing much judgment:

- inspect repository files
- create a Python virtual environment
- install Python dependencies
- install Playwright Chromium
- copy `config/.env.example` to `.env`
- explain missing environment variables
- run local validation and smoke tests
- run `scan`
- help the user interpret scan output

---

## 4) What the user must provide or do manually

An agent should **not assume** it can infer or fabricate these values.

The user must provide:
- `PANCAKE_PAGE_ID`
- `PANCAKE_PAGE_ACCESS_TOKEN`
- `PANCAKE_PAGE_URL`
- preferred `PANCAKE_PAGE_KEY` label
- a local Chromium/Chrome/Brave path if defaults do not match the machine
- a local browser profile path already logged into Pancake
- a CDP port or URL if non-default
- the follow-up message template to use in production
- operational limits such as `PANCAKE_MAX_SEND_PER_RUN`

The user must also manually confirm:
- Pancake is logged in inside the chosen browser profile
- the chosen browser profile belongs to the intended account/page
- the message template is approved for their business/compliance policy
- it is acceptable to move from `scan` to `send`

---

## 5) Questions the agent should ask the user before setup

Ask these clearly and in order.

### Required configuration questions
1. What is your **Pancake page ID**?
2. What is your **Pancake page access token**?
3. What is your **Pancake page URL**?
4. What label would you like for `PANCAKE_PAGE_KEY`? (example: `my-page`)
5. Which browser do you want to use for CDP attach: **Chromium, Chrome, or Brave**?
6. What is the **browser executable path** on your machine?
7. What is the **browser profile path** that is already logged into Pancake?
8. What CDP port do you want to use? (default `9239` is fine if unused)
9. What follow-up message template should the script send?
10. What should `PANCAKE_MAX_SEND_PER_RUN` be for first tests? (recommend `1`)

### Safety confirmation questions
11. Have you already logged into Pancake in that browser profile?
12. Do you want to run **scan only first** before any send attempt?
13. Do you want the script to start Chromium automatically if CDP is not already running?
14. Are there any internal tags beyond `ĐÃ CHỐT` and `KHÔNG MUA` that should be excluded later?

If the user cannot answer these yet, the agent should pause and collect them before proceeding.

---

## 6) Recommended installation flow for agents

Follow this sequence.

### Step 1: inspect the repo
Read at least:
- `README.md`
- `config/.env.example`
- `scripts/run_followup.sh`
- `scripts/smoke_test.sh`
- `src/pancake_followup.py`

### Step 2: create environment
Recommended commands:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

### Step 3: create `.env`

```bash
cp config/.env.example .env
```

Then fill in real values from the user.

### Step 4: validate local setup
Run:

```bash
./scripts/smoke_test.sh
```

### Step 5: confirm browser login state
Before running anything sensitive, confirm with the user:
- the chosen browser profile exists
- it is already logged into Pancake
- the configured `PANCAKE_PAGE_URL` is correct

### Step 6: run scan only first
Run:

```bash
set -a && source .env && set +a
python src/pancake_followup.py scan
```

The agent should review the output with the user before moving on.

### Step 7: run first safe send test
Only after explicit user confirmation:
- set `PANCAKE_MAX_SEND_PER_RUN=1`
- run the sender once

```bash
./scripts/run_followup.sh
```

### Step 8: inspect outputs
Review:
- `data/pancake-followup-queue.json`
- `data/pancake-followup-last-run.json`
- `data/pancake-followup-state.json`

Only after a good first run should the user increase throughput.

---

## 7) First-run safe mode policy

Agents should strongly prefer this first-run sequence:

1. install dependencies
2. configure `.env`
3. confirm Pancake login in browser profile
4. run `scan`
5. inspect candidates with the user
6. set `PANCAKE_MAX_SEND_PER_RUN=1`
7. run one controlled send
8. inspect results JSON
9. only then discuss cron or larger batch sizes

Do **not** jump straight to large-volume sends.

---

## 8) Operational guardrails for agents

### Do
- prefer `scan` first
- ask for missing inputs explicitly
- use conservative defaults
- recommend `PANCAKE_MAX_SEND_PER_RUN=1` for the first send test
- explain which files contain runtime state
- remind the user not to commit `.env` or runtime JSON files

### Do not
- invent page IDs, tokens, or browser paths
- assume the browser profile is already logged in
- encourage sending at scale before a successful first-run validation
- claim compliance/legal suitability without the user reviewing their own policies
- commit `.env`, real customer JSON, screenshots, or logs with customer content

---

## 9) Common failure modes and how an agent should respond

### `Missing required env: ...`
Meaning:
- the `.env` file is incomplete or not loaded

Agent response:
- identify the exact missing variable
- ask the user for the real value
- do not guess

### `cdp_attach_failed`
Meaning:
- the browser was not reachable at the configured CDP URL

Agent response:
- confirm browser path
- confirm CDP port
- confirm the browser profile exists
- check whether Chromium was started with remote debugging

### `attached_session_has_no_pancake_tab`
Meaning:
- browser CDP attach worked but no Pancake tab existed in the attached context

Agent response:
- ask the user to open Pancake in that profile
- or navigate to `PANCAKE_PAGE_URL` and confirm login

### `conversation_search_input_not_found`
Meaning:
- UI layout differs or Pancake is not on the expected screen

Agent response:
- confirm the user is on the right page
- inspect UI manually before retrying

### `comment_ui_detected_skip`
Meaning:
- the script deliberately refused to send because it looked like a comment thread, not a Messenger chat

Agent response:
- treat as a safe skip, not a bug by default

### `post_send_message_not_detected_message`
Meaning:
- the script could not verify the message appeared after send

Agent response:
- inspect the thread manually before retrying
- prefer caution over retry spam

---

## 10) Files agents should mention to users

Important files:
- `README.md` → human-readable overview
- `config/.env.example` → configuration template
- `scripts/run_followup.sh` → standard runner
- `scripts/smoke_test.sh` → lightweight setup validator
- `docs/sample-scan-output.json` → sanitized example output
- `src/pancake_followup.py` → main logic

Runtime-generated files:
- `data/pancake-followup-state.json`
- `data/pancake-followup-queue.json`
- `data/pancake-followup-last-run.json`

Agents should remind users that runtime files may contain operational data and should not be committed publicly.

---

## 11) Minimal setup script the agent may suggest

If the user wants a minimal command sequence, the agent may suggest:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
cp config/.env.example .env
./scripts/smoke_test.sh
```

Then the agent should stop and ask the user for the real `.env` values.

---

## 12) Public repo hygiene reminders

If helping the user prepare a public GitHub repo, agents should verify:
- `.env` is not committed
- no real tokens exist anywhere in tracked files
- no real customer data exists in `data/`
- no screenshots/logs with customer content are tracked
- `.env.example` uses placeholders only
- sample output is sanitized

---

## 13) Recommended agent behavior summary

If you are an AI agent reading this repo for the first time:

1. understand the project as a cautious Pancake follow-up workflow
2. collect missing setup inputs from the user explicitly
3. install dependencies
4. create and validate `.env`
5. confirm browser login state manually with the user
6. run `scan`
7. review results with the user
8. run a **single-message first test** only after explicit approval
9. inspect output files
10. only then discuss automation/cron/scale-up

That is the intended operator-friendly workflow for this repository.
