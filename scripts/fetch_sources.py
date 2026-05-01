from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import feedparser
import requests
import yaml

from hash_utils import compute_content_hash
from sqlite_ops import get_conn, upsert


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "neican.sqlite"
SOURCES_PATH = ROOT / "config" / "sources.yaml"

HTTP_TIMEOUT = 30
HTTP_HEADERS = {
    "User-Agent": "neican-ai/0.1 (knowledge engine; +https://neican.ai)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


@dataclass(frozen=True)
class FetchResult:
    inserted_count: int = 0
    skipped_duplicate_count: int = 0
    failed_count: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "inserted_count": self.inserted_count,
            "skipped_duplicate_count": self.skipped_duplicate_count,
            "failed_count": self.failed_count,
        }


def load_sources(sources_path: Path, source_name: str | None = None) -> list[dict[str, Any]]:
    data = yaml.safe_load(sources_path.read_text(encoding="utf-8")) or {}
    sources = data.get("sources") or []
    enabled_rss_sources = [
        source
        for source in sources
        if source.get("enabled", True) and source.get("type") == "rss"
    ]
    if source_name:
        enabled_rss_sources = [
            source for source in enabled_rss_sources if source.get("name") == source_name
        ]
    return enabled_rss_sources


def entry_text(entry: Any) -> str:
    """Return the best available text from RSS entry (content > summary > description)."""
    content = entry.get("content")
    if content and isinstance(content, list):
        values = [item.get("value", "") for item in content if isinstance(item, dict)]
        if values:
            return "\n\n".join(value for value in values if value)
    return entry.get("summary") or entry.get("description") or ""


def is_short_form_url(url: str) -> bool:
    """Return True if the URL points to a short-form page (newsflash, tweet, etc)."""
    short_patterns = [
        "/newsflashes/",  # 36kr 快讯
        "/newsflash/",
        "/brief/",
        "/bulletin/",
    ]
    return any(p in url for p in short_patterns)


def fetch_full_text(url: str) -> str | None:
    """Fetch original article HTML from URL. Returns raw HTML or None on failure.

    Skips short-form URLs (newsflashes etc) where the RSS summary is already sufficient.
    """
    if not url:
        return None
    if is_short_form_url(url):
        return None
    try:
        resp = requests.get(url, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
        ct = resp.headers.get("content-type", "")
        if "text/html" in ct or "application/xhtml" in ct:
            # Anti-bot check: if response is suspiciously short, it's likely a captcha
            if len(resp.text) < 3000:
                return None
            return resp.text
        return None
    except Exception as exc:
        print(f"    [WARN] full-text fetch failed for {url}: {exc}")
        return None


def entry_author(entry: Any) -> str | None:
    return entry.get("author") or entry.get("creator")


def entry_published_at(entry: Any) -> str | None:
    raw = entry.get("published") or entry.get("updated")
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
        return dt.strftime("%Y-%m-%dT%H:%M:%S") + _tz_offset(dt)
    except Exception:
        return raw


def _tz_offset(dt: datetime) -> str:
    off = dt.utcoffset()
    if off is None:
        return "Z"
    total = int(off.total_seconds())
    sign = "+" if total >= 0 else "-"
    h, m = divmod(abs(total), 3600)
    return f"{sign}{h:02d}:{m // 60:02d}"


def normalize_source(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": source["name"],
        "type": source["type"],
        "url": source["url"],
        "enabled": 1 if source.get("enabled", True) else 0,
        "trust_level": int(source.get("trust_level", 3)),
        "language": source.get("language", "en"),
        "fetch_interval_minutes": int(source.get("fetch_interval_minutes", 120)),
    }


def existing_hash(conn, content_hash: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM raw_items WHERE content_hash = ? LIMIT 1",
        (content_hash,),
    ).fetchone()
    return row is not None


def insert_raw_item(conn, source_id: int, entry: Any, full_text: str | None = None) -> None:
    source_url = entry.get("link") or entry.get("id")
    title = entry.get("title")
    published_at = entry_published_at(entry)
    content_hash = compute_content_hash(title, source_url, published_at)
    # Prefer full article HTML; fall back to RSS summary
    raw_text = full_text or entry_text(entry)
    conn.execute(
        """
        INSERT INTO raw_items (
          source_id, source_url, title, author, published_at, raw_text,
          content_hash, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 'new')
        """,
        (
            source_id,
            source_url,
            title,
            entry_author(entry),
            published_at,
            raw_text,
            content_hash,
        ),
    )


def write_run(conn, status: str, result: FetchResult, errors: list[str]) -> None:
    conn.execute(
        """
        INSERT INTO runs (run_type, status, output_json, error_message, finished_at)
        VALUES ('fetch_sources', ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            status,
            json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True),
            "\n".join(errors) if errors else None,
        ),
    )


def fetch_sources(
    db_path: Path = DB_PATH,
    sources_path: Path = SOURCES_PATH,
    limit: int | None = None,
    source_name: str | None = None,
    full_text: bool = False,
    dry_run: bool = False,
) -> FetchResult:
    db_path = Path(db_path)
    sources_path = Path(sources_path)
    if not dry_run and not db_path.exists():
        raise SystemExit("Database not found. Run: python3 scripts/init_db.py")

    inserted_count = 0
    skipped_duplicate_count = 0
    failed_count = 0
    attempted_count = 0
    errors: list[str] = []
    sources = load_sources(sources_path, source_name)

    with get_conn(db_path) as conn:
        source_ids: dict[str, int] = {}
        if not dry_run:
            for source in sources:
                normalized_source = normalize_source(source)
                upsert(conn, "sources", normalized_source, "url")
                source_row = conn.execute(
                    "SELECT id FROM sources WHERE url = ?",
                    (normalized_source["url"],),
                ).fetchone()
                source_ids[source["url"]] = int(source_row["id"])

        for source in sources:
            if limit is not None and attempted_count >= limit:
                break

            source_id = source_ids.get(source["url"])

            feed = feedparser.parse(source["url"])
            if getattr(feed, "bozo", False):
                failed_count += 1
                errors.append(f"{source['name']}: {getattr(feed, 'bozo_exception', 'feed parse error')}")
                continue

            for entry in feed.entries:
                if limit is not None and attempted_count >= limit:
                    break
                attempted_count += 1
                try:
                    source_url = entry.get("link") or entry.get("id")
                    title = entry.get("title")
                    published_at = entry_published_at(entry)
                    content_hash = compute_content_hash(title, source_url, published_at)
                    if not source_url:
                        failed_count += 1
                        errors.append(f"{source['name']}: item missing source_url")
                        continue

                    if not dry_run and existing_hash(conn, content_hash):
                        skipped_duplicate_count += 1
                        continue

                    inserted_count += 1
                    # Fetch full article HTML when requested
                    html = None
                    if full_text and source_url:
                        html = fetch_full_text(source_url)
                    if not dry_run:
                        insert_raw_item(conn, source_id, entry, full_text=html)
                except Exception as exc:  # Keep batch collection alive.
                    failed_count += 1
                    errors.append(f"{source['name']}: {exc}")

        result = FetchResult(inserted_count, skipped_duplicate_count, failed_count)
        if not dry_run:
            if failed_count and inserted_count == 0 and skipped_duplicate_count == 0:
                status = "failed"
            elif failed_count:
                status = "partial_failed"
            else:
                status = "success"
            write_run(conn, status, result, errors)
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch RSS sources into raw_items.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--source", dest="source_name", default=None)
    parser.add_argument("--full-text", action="store_true", help="Fetch full article HTML via HTTP (not just RSS summary)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = fetch_sources(
        limit=args.limit,
        source_name=args.source_name,
        full_text=args.full_text,
        dry_run=args.dry_run,
    )
    print(
        "[OK] fetch_sources "
        f"inserted={result.inserted_count} "
        f"duplicates={result.skipped_duplicate_count} "
        f"failed={result.failed_count}"
    )


if __name__ == "__main__":
    main()
