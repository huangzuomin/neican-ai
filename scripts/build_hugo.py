from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlite_ops import get_conn


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "neican.sqlite"
SITE_DIR = ROOT / "hugo-site"
LOGS_DIR = ROOT / "logs" / "build"
LOCAL_HUGO_BIN = ROOT / ".tools" / "hugo" / "hugo"


@dataclass(frozen=True)
class BuildResult:
    success: bool
    log_path: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "log_path": self.log_path,
            "success": self.success,
        }


class _HrefParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        for name, value in attrs:
            if name == "href" and value:
                self.hrefs.append(value)


def write_failure_log(logs_dir: Path, content: str) -> Path:
    logs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = logs_dir / f"{timestamp}.log"
    path.write_text(content, encoding="utf-8")
    return path


def write_run(conn, status: str, result: BuildResult, error_message: str | None = None) -> None:
    conn.execute(
        """
        INSERT INTO runs (run_type, status, output_json, error_message, finished_at)
        VALUES ('hugo_build', ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            status,
            json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True),
            error_message,
        ),
    )


def find_broken_internal_links(public_dir: Path) -> list[str]:
    """Return internal hrefs that do not resolve to built files."""
    if not public_dir.exists():
        return []
    broken: list[str] = []
    html_files = sorted(public_dir.rglob("*.html"))
    for html_file in html_files:
        parser = _HrefParser()
        parser.feed(html_file.read_text(encoding="utf-8", errors="ignore"))
        for href in parser.hrefs:
            target = href.split("#", 1)[0].split("?", 1)[0]
            if not target or target.startswith(("http://", "https://", "mailto:", "tel:")):
                continue
            if target.startswith("//"):
                continue
            if target.startswith("/"):
                candidate = public_dir / target.lstrip("/")
            else:
                candidate = html_file.parent / target
            if candidate.is_dir():
                candidate = candidate / "index.html"
            elif candidate.suffix == "":
                candidate = candidate / "index.html"
            if not candidate.exists():
                broken.append(f"{html_file.relative_to(public_dir)} -> {href}")
    return broken


def build_hugo(
    site_dir: Path = SITE_DIR,
    db_path: Path = DB_PATH,
    logs_dir: Path = LOGS_DIR,
) -> BuildResult:
    site_dir = Path(site_dir)
    db_path = Path(db_path)
    logs_dir = Path(logs_dir)
    if not db_path.exists():
        raise SystemExit("Database not found. Run: python3 scripts/init_db.py")

    hugo_bin = str(LOCAL_HUGO_BIN if LOCAL_HUGO_BIN.exists() else "hugo")
    error_message = None
    try:
        completed = subprocess.run(
            [hugo_bin, "--gc", "--minify"],
            cwd=site_dir,
            text=True,
            capture_output=True,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        if completed.returncode == 0:
            broken_links = find_broken_internal_links(site_dir / "public")
            if broken_links:
                error_message = "internal link check failed"
                log_path = write_failure_log(logs_dir, "\n".join(broken_links))
                result = BuildResult(success=False, log_path=str(log_path))
                with get_conn(db_path) as conn:
                    write_run(conn, "failed", result, error_message)
                return result
            result = BuildResult(success=True)
            with get_conn(db_path) as conn:
                write_run(conn, "success", result)
            return result
        error_message = f"hugo exited with code {completed.returncode}"
        log_path = write_failure_log(logs_dir, output or error_message)
    except FileNotFoundError:
        error_message = "hugo executable not found"
        log_path = write_failure_log(logs_dir, error_message)

    result = BuildResult(success=False, log_path=str(log_path))
    with get_conn(db_path) as conn:
        write_run(conn, "failed", result, error_message)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Hugo build checks.")
    parser.add_argument("--site-dir", type=Path, default=SITE_DIR)
    args = parser.parse_args()

    result = build_hugo(site_dir=args.site_dir)
    if result.success:
        print("[OK] Hugo build succeeded")
        return
    print(f"[ERROR] Hugo build failed; log={result.log_path}")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
