#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from playwright.sync_api import sync_playwright

VN_TZ = timezone(timedelta(hours=7))
EXCLUDED_TAGS = {"ĐÃ CHỐT", "KHÔNG MUA"}
MESSAGE_TEMPLATE = os.environ.get(
    "PANCAKE_MESSAGE_TEMPLATE",
    "Hi anh/chị, em follow up lại cuộc trao đổi trước. Nếu anh/chị vẫn còn quan tâm, em có thể gửi thêm thông tin chi tiết để mình tham khảo nhanh ạ.",
)
MESSAGE_HASH = hashlib.sha256(MESSAGE_TEMPLATE.encode("utf-8")).hexdigest()[:16]


@dataclass
class AppConfig:
    page_key: str
    page_id: str
    page_access_token: str
    api_base: str
    page_url: str
    cdp_url: str
    max_send_per_run: int
    state_path: Path
    queue_path: Path
    results_path: Path
    scan_days: float
    lookback_days: int
    scan_limit: int


def now_vn() -> str:
    return datetime.now(VN_TZ).isoformat()


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def require_env(name: str) -> str:
    value = env(name)
    if not value:
        raise RuntimeError(f"Missing required env: {name}")
    return value


def load_config() -> AppConfig:
    workspace = Path(env("PANCAKE_WORKSPACE_DIR", ".")).resolve()
    data_dir = Path(env("PANCAKE_DATA_DIR", str(workspace / "data"))).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)

    return AppConfig(
        page_key=require_env("PANCAKE_PAGE_KEY"),
        page_id=require_env("PANCAKE_PAGE_ID"),
        page_access_token=require_env("PANCAKE_PAGE_ACCESS_TOKEN"),
        api_base=env("PANCAKE_API_BASE", "https://pages.fm/api/public_api").rstrip("/"),
        page_url=require_env("PANCAKE_PAGE_URL"),
        cdp_url=env("PANCAKE_CHROMIUM_CDP_URL", "http://127.0.0.1:9239"),
        max_send_per_run=int(env("PANCAKE_MAX_SEND_PER_RUN", "5")),
        state_path=Path(env("PANCAKE_STATE_PATH", str(data_dir / "pancake-followup-state.json"))).resolve(),
        queue_path=Path(env("PANCAKE_QUEUE_PATH", str(data_dir / "pancake-followup-queue.json"))).resolve(),
        results_path=Path(env("PANCAKE_RESULTS_PATH", str(data_dir / "pancake-followup-last-run.json"))).resolve(),
        scan_days=float(env("PANCAKE_SCAN_DAYS", "2")),
        lookback_days=int(env("PANCAKE_LOOKBACK_DAYS", "14")),
        scan_limit=int(env("PANCAKE_SCAN_LIMIT", "100")),
    )


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def queue_key(conversation_id: str, fb: str) -> str:
    return f"{conversation_id}::{fb}::{MESSAGE_HASH}"


def parse_dt(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=VN_TZ)
        return dt.astimezone(VN_TZ)
    except Exception:
        return None


def normalize_tags(conv: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for t in conv.get("tags") or []:
        if isinstance(t, dict):
            txt = (t.get("text") or "").strip()
            if txt:
                out.append(txt)
        elif isinstance(t, str) and t.strip():
            out.append(t.strip())
    return out


def normalize_customer(conv: dict[str, Any]) -> dict[str, Any]:
    customers = conv.get("customers") or []
    if customers and isinstance(customers[0], dict):
        return customers[0]
    return {}


def normalize_assignees(conv: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for item in conv.get("current_assign_users") or []:
        if isinstance(item, dict):
            names.append(item.get("name") or item.get("full_name") or str(item.get("id") or ""))
    if not names:
        names = [str(x) for x in (conv.get("assignee_ids") or []) if x]
    return names


def fetch_conversations(cfg: AppConfig, since_ts: int, until_ts: int, lookback_pages: int = 10) -> list[dict[str, Any]]:
    url = f"{cfg.api_base}/v1/pages/{cfg.page_id}/conversations"
    all_items: list[dict[str, Any]] = []
    page_number = 1
    session = requests.Session()
    while page_number <= lookback_pages:
        resp = session.get(url, params={
            "page_access_token": cfg.page_access_token,
            "since": since_ts,
            "until": until_ts,
            "page_number": page_number,
        }, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("conversations", [])
        if not items:
            break
        all_items.extend(items)
        if len(items) < 10:
            break
        page_number += 1
    return all_items


def run_scan(cfg: AppConfig) -> dict[str, Any]:
    now = datetime.now(VN_TZ)
    cutoff = now - timedelta(days=cfg.scan_days)
    since = int((now - timedelta(days=cfg.lookback_days)).timestamp())
    until = int(now.timestamp())

    raw = fetch_conversations(cfg, since, until)
    candidates: list[dict[str, Any]] = []
    excluded_summary = {
        "excluded_by_tag": 0,
        "excluded_last_sender_not_page": 0,
        "excluded_not_old_enough": 0,
        "excluded_missing_updated_at": 0,
    }

    for conv in raw:
        tags = normalize_tags(conv)
        if EXCLUDED_TAGS.intersection(tags):
            excluded_summary["excluded_by_tag"] += 1
            continue

        last_sent_by = conv.get("last_sent_by") or {}
        if str(last_sent_by.get("id") or "") != cfg.page_id:
            excluded_summary["excluded_last_sender_not_page"] += 1
            continue

        updated_at = parse_dt(conv.get("updated_at") or "")
        if not updated_at:
            excluded_summary["excluded_missing_updated_at"] += 1
            continue
        if updated_at > cutoff:
            excluded_summary["excluded_not_old_enough"] += 1
            continue

        customer = normalize_customer(conv)
        candidates.append({
            "conversation_id": conv.get("id"),
            "customer_name": customer.get("name") or "Unknown customer",
            "customer_fb_id": customer.get("fb_id"),
            "updated_at": updated_at.isoformat(),
            "silent_hours": round((now - updated_at).total_seconds() / 3600, 1),
            "snippet": conv.get("snippet"),
            "tags": tags,
            "assignees": normalize_assignees(conv),
            "last_sent_by_admin": last_sent_by.get("admin_name"),
        })

    candidates.sort(key=lambda x: x["updated_at"])
    candidates = candidates[: cfg.scan_limit]
    return {
        "success": True,
        "action": "scan",
        "page_key": cfg.page_key,
        "page_id": cfg.page_id,
        "rule": {
            "last_sender": "page/admin",
            "silent_days_gte": cfg.scan_days,
            "excluded_tags": sorted(EXCLUDED_TAGS),
        },
        "totals": {
            "raw_conversations": len(raw),
            "eligible_returned": len(candidates),
            **excluded_summary,
        },
        "candidates": candidates,
    }


def build_queue(candidates: list[dict[str, Any]], state: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    pending = state.setdefault("pending_locks", {})
    sent_ids = set(str(x) for x in state.get("sent_customer_fb_ids", []))
    queued = []
    skipped = []
    seen_keys = set()
    seen_fb = set()

    for c in candidates:
        fb = str(c.get("customer_fb_id") or "").strip()
        conversation_id = str(c.get("conversation_id") or "").strip()
        name = c.get("customer_name") or "Unknown customer"
        if not fb or not conversation_id:
            skipped.append({"name": name, "fb": fb, "conversation_id": conversation_id, "reason": "missing_fb_or_conversation_id"})
            continue

        key = queue_key(conversation_id, fb)
        pending_item = pending.get(key)
        if fb in sent_ids:
            skipped.append({"name": name, "fb": fb, "conversation_id": conversation_id, "reason": "already_sent_previous_run"})
            continue
        if pending_item and pending_item.get("status") in {"pending", "sent"}:
            skipped.append({"name": name, "fb": fb, "conversation_id": conversation_id, "reason": "already_locked"})
            continue
        if fb in seen_fb:
            skipped.append({"name": name, "fb": fb, "conversation_id": conversation_id, "reason": "duplicate_customer_fb_id_in_queue"})
            continue
        if key in seen_keys:
            skipped.append({"name": name, "fb": fb, "conversation_id": conversation_id, "reason": "duplicate_in_queue"})
            continue

        seen_keys.add(key)
        seen_fb.add(fb)
        queued.append({
            "queue_key": key,
            "customer_name": name,
            "customer_fb_id": fb,
            "conversation_id": conversation_id,
            "status": "queued",
        })

    return queued, skipped


def open_browser_page(cfg: AppConfig, playwright):
    try:
        browser = playwright.chromium.connect_over_cdp(cfg.cdp_url)
    except Exception as e:
        raise RuntimeError(f"cdp_attach_failed: {e}") from e
    if not browser.contexts:
        browser.close()
        raise RuntimeError("attached_cdp_has_no_contexts")
    context = browser.contexts[0]
    page = None
    for p in context.pages:
        try:
            url = p.url or ""
        except Exception:
            url = ""
        if "pancake.vn" in url:
            page = p
            break
    if page is None:
        browser.close()
        raise RuntimeError("attached_session_has_no_pancake_tab")
    return browser, context, page


def is_visible_editor(item) -> bool:
    try:
        box = item.bounding_box()
    except Exception:
        box = None
    return bool(box and box["width"] > 100 and box["height"] > 20)


def find_editor(page, ui_kind: str | None = None):
    selector_groups = {
        "comment": ["textarea", "[contenteditable=\"true\"]", "div[role=\"textbox\"]"],
        "message": ["textarea", "[contenteditable=\"true\"]", "div[role=\"textbox\"]", "div.public-DraftEditor-content", "div.notranslate[contenteditable=\"true\"]"],
        "unknown": ["textarea", "[contenteditable=\"true\"]", "div[role=\"textbox\"]", "div.public-DraftEditor-content", "div.notranslate[contenteditable=\"true\"]"],
    }
    selectors = selector_groups.get(ui_kind or "unknown", selector_groups["unknown"])
    for sel in selectors:
        loc = page.locator(sel)
        try:
            count = loc.count()
        except Exception:
            continue
        for i in range(count):
            item = loc.nth(i)
            if is_visible_editor(item):
                return item
    return None


def ensure_conversation_workspace(page) -> None:
    list_selectors = [
        "#conversationList",
        "[class*=\"conversation-list\"]",
        "[class*=\"conversationList\"]",
        "[class*=\"conversation-menu\"]",
        "[data-testid*=\"conversation\"]",
        "input.conversation-menu-search-input",
        "input[placeholder*=\"Tìm\"]",
        "input[placeholder*=\"tìm\"]",
    ]
    body_markers = ["Lọc theo", "Hội thoại", "Tin nhắn"]

    for _ in range(2):
        for sel in list_selectors:
            try:
                loc = page.locator(sel)
                if loc.count() > 0:
                    try:
                        if loc.first.is_visible():
                            return
                    except Exception:
                        return
            except Exception:
                continue

        try:
            body_text = page.locator("body").inner_text(timeout=5000)
        except Exception:
            body_text = ""
        if body_text and all(marker in body_text for marker in body_markers[:1]):
            return

        nav_candidates = ["text=Hội thoại", "text=Tin nhắn", "[href*=\"inbox\"]", "[href*=\"conversation\"]"]
        clicked = False
        for sel in nav_candidates:
            loc = page.locator(sel).first
            try:
                if loc.count() > 0 and loc.is_visible():
                    loc.click(timeout=5000)
                    page.wait_for_timeout(2000)
                    clicked = True
                    break
            except Exception:
                continue
        if not clicked:
            break

    body_preview = ""
    try:
        body_preview = page.locator("body").inner_text(timeout=5000)[:500]
    except Exception:
        pass
    raise RuntimeError(f"conversation_list_not_found_on_logged_in_session: {page.url} | body={body_preview}")


def find_search_input(page):
    selectors = [
        "input.conversation-menu-search-input",
        "input[placeholder*=\"Tìm\"]",
        "input[placeholder*=\"tìm\"]",
        "input[type=\"search\"]",
    ]
    for sel in selectors:
        loc = page.locator(sel)
        try:
            count = loc.count()
        except Exception:
            continue
        for i in range(count):
            item = loc.nth(i)
            if is_visible_editor(item):
                return item
            try:
                if item.is_visible():
                    return item
            except Exception:
                continue
    raise RuntimeError("conversation_search_input_not_found")


def reveal_conversation_in_search(page, customer_name: str) -> None:
    ensure_conversation_workspace(page)
    search = find_search_input(page)
    search.click(timeout=10000)
    page.keyboard.press("Meta+A")
    page.keyboard.press("Backspace")
    search.fill(customer_name)
    page.keyboard.press("Enter")
    page.wait_for_timeout(1800)


def get_thread_text(page) -> str:
    selectors = ["#messageCol", "#message-col-list", ".message-col-list", ".conversation-detail", ".chat-content"]
    for sel in selectors:
        loc = page.locator(sel)
        try:
            if loc.count() > 0:
                txt = loc.first.inner_text(timeout=5000)
                if txt:
                    return txt
        except Exception:
            continue
    return ""


def thread_has_comment_uid(thread_text: str) -> bool:
    import re
    return bool(re.search(r"\b\d{6,}_\d{6,}\b", thread_text or ""))


def detect_ui_kind(page) -> str:
    thread_text = get_thread_text(page)
    if thread_has_comment_uid(thread_text):
        return "comment"

    lowered = thread_text.lower()
    comment_markers = [
        "bạn đang phản hồi bình luận của người dùng",
        "phản hồi bình luận",
        "bài viết trên trang của mình",
        "link facebook",
        "bình luận",
        "trả lời bình luận",
    ]
    message_markers = ["tin nhắn", "nhập tin nhắn", "gửi tin nhắn", "hội thoại"]
    if any(marker in lowered for marker in comment_markers):
        return "comment"
    if any(marker in lowered for marker in message_markers):
        return "message"
    return "message"


def click_search_result_candidates(page, conversation_id: str, customer_name: str) -> tuple[bool, str]:
    tried = []
    handle = page.evaluate_handle("cid => document.getElementById(cid)", conversation_id)
    el = handle.as_element()
    if el is not None:
        try:
            el.click(timeout=10000)
            page.wait_for_timeout(1800)
            ui_kind = detect_ui_kind(page)
            if ui_kind == "comment":
                tried.append("target_id_is_comment")
            else:
                return True, "target_id"
        except Exception as e:
            tried.append(f"target_id_click_failed:{e}")

    candidate_selectors = [f'text="{customer_name}"', f':text("{customer_name}")']
    for sel in candidate_selectors:
        try:
            loc = page.locator(sel)
            count = min(loc.count(), 5)
        except Exception:
            continue
        for i in range(count):
            item = loc.nth(i)
            try:
                if not item.is_visible():
                    continue
                item.click(timeout=10000)
                page.wait_for_timeout(1800)
                ui_kind = detect_ui_kind(page)
                if ui_kind == "comment":
                    tried.append(f"candidate_{i}_comment")
                    continue
                return True, f"candidate_{i}"
            except Exception as e:
                tried.append(f"candidate_{i}_click_failed:{e}")
                continue

    if el is None:
        return False, "conversation_id_not_visible_in_list"
    return False, "no_messenger_candidate_after_search|" + ";".join(tried[:10])


def open_conversation_by_id(page, conversation_id: str, customer_name: str) -> tuple[bool, str]:
    reveal_conversation_in_search(page, customer_name)
    ok, source = click_search_result_candidates(page, conversation_id, customer_name)
    if not ok:
        return False, source
    thread_text = get_thread_text(page)
    ui_kind = detect_ui_kind(page)
    if customer_name not in thread_text and ui_kind == "comment":
        return False, "opened_comment_not_confirmed"
    if ui_kind == "comment":
        return False, "comment_ui_detected_skip"
    return True, source


def message_already_present(page) -> bool:
    thread_text = get_thread_text(page)
    return MESSAGE_TEMPLATE in thread_text


def send_one(page, conversation_id: str, customer_name: str) -> tuple[bool, str]:
    ok, reason = open_conversation_by_id(page, conversation_id, customer_name)
    if not ok:
        return False, reason

    ui_kind = detect_ui_kind(page)
    if message_already_present(page):
        return False, f"{ui_kind}_message_already_present_in_thread"

    editor = find_editor(page, ui_kind=ui_kind)
    if editor is None:
        return False, f"no_visible_editor_{ui_kind}"

    editor.click(timeout=10000)
    try:
        editor.fill("")
        editor.fill(MESSAGE_TEMPLATE, timeout=10000)
    except Exception:
        page.keyboard.press("Meta+A")
        page.keyboard.press("Backspace")
        page.keyboard.type(MESSAGE_TEMPLATE, delay=5)

    page.wait_for_timeout(300)
    page.keyboard.press("Enter")
    page.wait_for_timeout(1800)

    if not message_already_present(page):
        return False, f"post_send_message_not_detected_{ui_kind}"
    return True, ui_kind


def command_scan(cfg: AppConfig) -> int:
    result = run_scan(cfg)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def command_send(cfg: AppConfig) -> int:
    state = load_json(cfg.state_path, {"sent_customer_fb_ids": [], "history": [], "pending_locks": {}})
    scan = run_scan(cfg)
    candidates = scan.get("candidates", [])
    queue, pre_skipped = build_queue(candidates, state)
    queue = queue[: cfg.max_send_per_run]
    save_json(cfg.queue_path, {"generatedAt": now_vn(), "maxSendPerRun": cfg.max_send_per_run, "items": queue})

    results = {
        "startedAt": now_vn(),
        "scanTotals": scan.get("totals", {}),
        "maxSendPerRun": cfg.max_send_per_run,
        "queuedCount": len(queue),
        "preSkipped": pre_skipped,
        "sent": [],
        "failed": [],
        "finishedAt": None,
    }

    with sync_playwright() as p:
        browser, context, page = open_browser_page(cfg, p)
        try:
            page.goto(cfg.page_url, wait_until="domcontentloaded", timeout=120000)
        except Exception as e:
            raise RuntimeError(f"pancake_initial_navigation_failed: {e}") from e
        page.wait_for_timeout(4000)

        current_url = page.url or ""
        if "pancake.vn" not in current_url:
            raise RuntimeError(f"wrong_attached_tab_url: {current_url}")
        ensure_conversation_workspace(page)

        processed = 0
        for item in queue:
            if processed >= cfg.max_send_per_run:
                break

            name = item["customer_name"]
            fb = item["customer_fb_id"]
            conversation_id = item["conversation_id"]
            qk = item["queue_key"]
            state.setdefault("pending_locks", {})[qk] = {
                "at": now_vn(),
                "name": name,
                "fb": fb,
                "conversation_id": conversation_id,
                "status": "pending",
            }
            save_json(cfg.state_path, state)

            try:
                ok, note = send_one(page, conversation_id, name)
                if ok:
                    processed += 1
                    results["sent"].append({"name": name, "fb": fb, "conversation_id": conversation_id})
                    if fb not in state.setdefault("sent_customer_fb_ids", []):
                        state["sent_customer_fb_ids"].append(fb)
                    state.setdefault("history", []).append({
                        "at": now_vn(),
                        "name": name,
                        "fb": fb,
                        "conversation_id": conversation_id,
                        "status": "sent",
                    })
                    state["pending_locks"][qk]["status"] = "sent"
                else:
                    results["failed"].append({"name": name, "fb": fb, "conversation_id": conversation_id, "reason": note})
                    state["pending_locks"][qk]["status"] = "failed"
                    state["pending_locks"][qk]["reason"] = note
                save_json(cfg.state_path, state)
            except Exception as e:
                results["failed"].append({"name": name, "fb": fb, "conversation_id": conversation_id, "reason": str(e)})
                state["pending_locks"][qk]["status"] = "failed"
                state["pending_locks"][qk]["reason"] = str(e)
                save_json(cfg.state_path, state)
                continue

        browser.close()

    results["finishedAt"] = now_vn()
    results["summary"] = {
        "sent_count": len(results["sent"]),
        "failed_count": len(results["failed"]),
        "pre_skipped_count": len(results["preSkipped"]),
    }
    save_json(cfg.results_path, results)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print("\n=== FOLLOWUP_SUMMARY ===")
    print(f"sent_count={results['summary']['sent_count']}")
    print(f"failed_count={results['summary']['failed_count']}")
    print(f"pre_skipped_count={results['summary']['pre_skipped_count']}")
    if results["failed"]:
        print("failed_customers=" + ", ".join(f"{x.get('name')}({x.get('reason')})" for x in results["failed"]))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pancake daily customer follow-up")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("scan")
    sub.add_parser("send")
    return parser


def main() -> int:
    cfg = load_config()
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "scan":
        return command_scan(cfg)
    if args.command == "send":
        return command_send(cfg)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
