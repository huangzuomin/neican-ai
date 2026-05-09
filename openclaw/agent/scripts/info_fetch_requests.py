from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from hash_utils import compute_content_hash
from sqlite_ops import get_conn


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "neican.sqlite"


@dataclass(frozen=True)
class InfoFetchConsumeResult:
    updated_count: int = 0
    failed_count: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "failed_count": self.failed_count,
            "updated_count": self.updated_count,
        }


def build_route_message(urls: list[str]) -> str:
    unique_urls = list(dict.fromkeys(url for url in urls if url))
    if not unique_urls:
        return ""
    lines = ["需要抓取：请抓取以下 URL 的全文，并将结果转发给 neican-editor："]
    lines.extend(f"- {url}" for url in unique_urls)
    return "\n".join(lines)


def enqueue_info_fetch_request(
    conn,
    source_url: str,
    title: str | None,
    reason: str,
    raw_item_id: int | None = None,
    priority: int = 5,
) -> bool:
    route_message = build_route_message([source_url])
    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO info_fetch_requests (
          raw_item_id, source_url, title, reason, priority, route_message, status
        )
        VALUES (?, ?, ?, ?, ?, ?, 'pending')
        """,
        (raw_item_id, source_url, title, reason, priority, route_message),
    )
    return cursor.rowcount > 0


def pending_route_message(conn, limit: int | None = None) -> str | None:
    sql = """
        SELECT source_url
        FROM info_fetch_requests
        WHERE status = 'pending'
        ORDER BY priority DESC, id
    """
    params: list[int] = []
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    urls = [row["source_url"] for row in conn.execute(sql, tuple(params)).fetchall()]
    message = build_route_message(urls)
    return message or None


def consume_info_fetch_results(
    results: list[dict],
    db_path: Path = DB_PATH,
) -> InfoFetchConsumeResult:
    updated_count = 0
    failed_count = 0
    with get_conn(db_path) as conn:
        for item in results:
            source_url = str(item.get("source_url") or item.get("url") or "").strip()
            clean_text = str(item.get("clean_text") or "").strip()
            if not source_url or not clean_text:
                failed_count += 1
                continue
            title = item.get("title")
            author = item.get("author")
            published_at = item.get("published_at")
            confidence = float(item.get("extraction_confidence") or 0.85)
            raw_text = str(item.get("raw_text") or clean_text)
            content_hash = compute_content_hash(title, source_url, published_at)
            payload_json = json.dumps(item, ensure_ascii=False, sort_keys=True)

            row = conn.execute(
                "SELECT raw_item_id FROM info_fetch_requests WHERE source_url = ? ORDER BY id DESC LIMIT 1",
                (source_url,),
            ).fetchone()
            raw_item_id = int(row["raw_item_id"]) if row and row["raw_item_id"] else None

            if raw_item_id:
                conn.execute(
                    """
                    UPDATE raw_items
                    SET title = COALESCE(?, title),
                        author = COALESCE(?, author),
                        published_at = COALESCE(?, published_at),
                        raw_text = ?,
                        clean_text = ?,
                        extraction_confidence = ?,
                        status = 'new',
                        error_message = NULL
                    WHERE id = ?
                    """,
                    (title, author, published_at, raw_text, clean_text, confidence, raw_item_id),
                )
            else:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO raw_items (
                      source_url, title, author, published_at, raw_text, clean_text,
                      content_hash, extraction_confidence, status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'new')
                    """,
                    (source_url, title, author, published_at, raw_text, clean_text, content_hash, confidence),
                )

            conn.execute(
                """
                UPDATE info_fetch_requests
                SET status = 'consumed',
                    result_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE source_url = ?
                """,
                (payload_json, source_url),
            )
            updated_count += 1
    return InfoFetchConsumeResult(updated_count=updated_count, failed_count=failed_count)
