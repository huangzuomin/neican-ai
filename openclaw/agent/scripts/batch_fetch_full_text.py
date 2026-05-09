"""Batch fetch full text for pending info_fetch_requests.

Reads pending URLs from info_fetch_requests, fetches full text via requests+BeautifulSoup,
updates raw_items with the fetched content, and marks requests as done.
"""
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "neican.sqlite"

HTTP_TIMEOUT = (5, 15)
HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; neican-ai/0.2; +https://neican.ai)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def fetch_full_text(url: str) -> dict:
    """Fetch URL and extract main text content."""
    try:
        resp = requests.get(url, timeout=HTTP_TIMEOUT, headers=HTTP_HEADERS, allow_redirects=True)
        resp.raise_for_status()
        ct = resp.headers.get("content-type", "")
        if "text/html" not in ct and "application/xhtml" not in ct:
            return {"success": False, "error": f"not HTML: {ct}", "text": None}

        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove script, style, nav, footer, header
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            tag.decompose()

        # Try article tag first
        article = soup.find("article")
        if article:
            text = article.get_text(separator="\n", strip=True)
        else:
            # Fall back to main content area
            main = soup.find("main") or soup.find("div", {"role": "main"}) or soup.body
            if main:
                text = main.get_text(separator="\n", strip=True)
            else:
                text = soup.get_text(separator="\n", strip=True)

        # Clean up excessive whitespace
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        text = "\n".join(lines)

        if len(text) < 200:
            return {"success": False, "error": f"too short ({len(text)} chars)", "text": None}

        return {"success": True, "error": None, "text": text}
    except Exception as e:
        return {"success": False, "error": str(e), "text": None}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, default=20, help="Number of URLs to fetch")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    pending = conn.execute(
        "SELECT id, source_url, title, raw_item_id FROM info_fetch_requests WHERE status = 'pending' ORDER BY id LIMIT ?",
        (args.batch,),
    ).fetchall()

    if not pending:
        print(json.dumps({"status": "no_pending", "fetched": 0}))
        conn.close()
        return

    success_count = 0
    fail_count = 0
    results = []

    for row in pending:
        url = row["source_url"]
        title = row["title"] or ""
        req_id = row["id"]
        raw_item_id = row["raw_item_id"]

        print(f"  Fetching [{req_id}]: {url[:80]}...", file=sys.stderr, flush=True)
        result = fetch_full_text(url)

        if result["success"]:
            success_count += 1
            status = "done"
            print(f"    ✓ {len(result['text'])} chars", file=sys.stderr, flush=True)

            if not args.dry_run and raw_item_id:
                # Update raw_items with fetched full text
                conn.execute(
                    "UPDATE raw_items SET raw_text = ?, status = 'fetched' WHERE id = ?",
                    (result["text"], raw_item_id),
                )
        else:
            fail_count += 1
            status = "failed"
            print(f"    ✗ {result['error']}", file=sys.stderr, flush=True)

        if not args.dry_run:
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
            conn.execute(
                "UPDATE info_fetch_requests SET status = ?, updated_at = ?, error_message = ? WHERE id = ?",
                (status, now, result["error"], req_id),
            )
            if result["success"] and result["text"]:
                conn.execute(
                    "UPDATE info_fetch_requests SET result_json = ? WHERE id = ?",
                    (json.dumps({"chars": len(result["text"]), "fetched_at": now}), req_id),
                )
            conn.commit()

        results.append({
            "id": req_id,
            "url": url,
            "status": status,
            "chars": len(result["text"]) if result["text"] else 0,
            "error": result["error"],
        })

        # Rate limit
        time.sleep(0.5)

    conn.close()

    output = {
        "status": "completed",
        "batch_size": len(pending),
        "success": success_count,
        "failed": fail_count,
        "remaining_pending": 0,  # will be checked separately
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
