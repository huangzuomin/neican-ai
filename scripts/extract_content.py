from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup

from sqlite_ops import get_conn


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "neican.sqlite"


@dataclass(frozen=True)
class ExtractResult:
    processed_count: int = 0
    failed_count: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "failed_count": self.failed_count,
            "processed_count": self.processed_count,
        }


def looks_like_html(text: str) -> bool:
    return bool(re.search(r"<\s*(html|body|article|main|section|div|p|h1|h2|script|nav)\b", text, re.I))


def normalize_text(text: str) -> str:
    lines = []
    for line in text.splitlines():
        collapsed = re.sub(r"[ \t]+", " ", line).strip()
        if collapsed:
            lines.append(collapsed)
        elif lines and lines[-1] != "":
            lines.append("")
    normalized = "\n".join(lines).strip()
    return re.sub(r"\n{3,}", "\n\n", normalized)


def clean_html(raw_text: str) -> str:
    soup = BeautifulSoup(raw_text, "html.parser")
    for tag in soup(["script", "style", "noscript", "iframe", "svg", "form", "nav", "footer", "header", "aside"]):
        tag.decompose()
    main = soup.find("article") or soup.find("main") or soup.body or soup
    return normalize_text(main.get_text("\n"))


def clean_text(raw_text: str) -> str:
    if looks_like_html(raw_text):
        return clean_html(raw_text)
    return normalize_text(raw_text)


def extraction_confidence(text: str, raw_text: str) -> float:
    if not text:
        return 0.0
    score = 0.45
    if len(text) >= 80:
        score += 0.25
    elif len(text) >= 20:
        score += 0.15
    if looks_like_html(raw_text):
        score += 0.15
    if len(text.split()) >= 8:
        score += 0.15
    return round(min(score, 1.0), 2)


def select_raw_items(conn, raw_item_id: int | None, batch: int | None):
    sql = """
        SELECT id, raw_text
        FROM raw_items
        WHERE status = 'new'
          AND clean_text IS NULL
    """
    params: list[int] = []
    if raw_item_id is not None:
        sql += " AND id = ?"
        params.append(raw_item_id)
    sql += " ORDER BY id"
    if batch is not None:
        sql += " LIMIT ?"
        params.append(batch)
    return conn.execute(sql, tuple(params)).fetchall()


def write_run(conn, status: str, result: ExtractResult, errors: list[str]) -> None:
    conn.execute(
        """
        INSERT INTO runs (run_type, status, output_json, error_message, finished_at)
        VALUES ('extract_content', ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            status,
            json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True),
            "\n".join(errors) if errors else None,
        ),
    )


def extract_content(
    db_path: Path = DB_PATH,
    raw_item_id: int | None = None,
    batch: int | None = None,
    dry_run: bool = False,
) -> ExtractResult:
    db_path = Path(db_path)
    if not dry_run and not db_path.exists():
        raise SystemExit("Database not found. Run: python3 scripts/init_db.py")

    processed_count = 0
    failed_count = 0
    errors: list[str] = []

    with get_conn(db_path) as conn:
        rows = select_raw_items(conn, raw_item_id, batch)
        for row in rows:
            item_id = int(row["id"])
            raw_text = row["raw_text"]
            try:
                if not raw_text or not raw_text.strip():
                    raise ValueError("raw_text is empty")
                cleaned = clean_text(raw_text)
                if not cleaned:
                    raise ValueError("clean_text is empty")
                confidence = extraction_confidence(cleaned, raw_text)
                processed_count += 1
                if not dry_run:
                    conn.execute(
                        """
                        UPDATE raw_items
                        SET clean_text = ?,
                            extraction_confidence = ?,
                            error_message = NULL
                        WHERE id = ?
                        """,
                        (cleaned, confidence, item_id),
                    )
            except Exception as exc:
                failed_count += 1
                message = str(exc)
                errors.append(f"raw_item_id={item_id}: {message}")
                if not dry_run:
                    conn.execute(
                        """
                        UPDATE raw_items
                        SET status = 'failed',
                            error_message = ?
                        WHERE id = ?
                        """,
                        (message, item_id),
                    )

        result = ExtractResult(processed_count, failed_count)
        if not dry_run:
            if failed_count and processed_count == 0:
                status = "failed"
            elif failed_count:
                status = "partial_failed"
            else:
                status = "success"
            write_run(conn, status, result, errors)
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract clean_text for raw_items.")
    parser.add_argument("--raw-item-id", type=int, default=None)
    parser.add_argument("--batch", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = extract_content(
        raw_item_id=args.raw_item_id,
        batch=args.batch,
        dry_run=args.dry_run,
    )
    print(
        "[OK] extract_content "
        f"processed={result.processed_count} "
        f"failed={result.failed_count}"
    )


if __name__ == "__main__":
    main()
