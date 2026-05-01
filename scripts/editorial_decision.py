from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from sqlite_ops import get_conn


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "neican.sqlite"
CONFIG_DIR = ROOT / "config"


@dataclass(frozen=True)
class DecisionResult:
    decided_count: int = 0
    failed_count: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "decided_count": self.decided_count,
            "failed_count": self.failed_count,
        }


@dataclass(frozen=True)
class Decision:
    grade: str
    action: str
    need_review: bool
    review_type: str | None
    reason: str


def load_rules(config_dir: Path) -> dict[str, Any]:
    path = Path(config_dir) / "editorial_rules.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def json_list(value: str | None) -> list[Any]:
    if not value:
        return []
    parsed = json.loads(value)
    return parsed if isinstance(parsed, list) else []


def select_events(conn, event_id: int | None, limit: int | None):
    sql = """
        SELECT events.*
        FROM events
        LEFT JOIN decisions ON decisions.event_id = events.id
        WHERE events.status = 'modeled'
          AND decisions.id IS NULL
    """
    params: list[int] = []
    if event_id is not None:
        sql += " AND events.id = ?"
        params.append(event_id)
    sql += " ORDER BY events.id"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    return conn.execute(sql, tuple(params)).fetchall()


def decide(event, rules: dict[str, Any]) -> Decision:
    grades = rules.get("grades") or {}
    a_rules = grades.get("A") or {}
    b_rules = grades.get("B") or {}
    d_rules = grades.get("D") or {}
    risk_threshold = int(a_rules.get("risk_score_max", 69)) + 1

    confidence = float(event["confidence"] or 0)
    risk_score = float(event["risk_score"] or 0)
    importance = float(event["importance_score"] or 0)
    seo = float(event["seo_value_score"] or 0)
    knowledge = float(event["knowledge_value_score"] or 0)
    entities = json_list(event["entities_json"])
    topics = json_list(event["topics_json"])

    if confidence < 0.5:
        return Decision("D", d_rules.get("action", "ignore"), False, None, "confidence < 0.5")

    if risk_score >= risk_threshold:
        return Decision("D", d_rules.get("action", "ignore"), True, "high_risk_content", "risk_score >= 70")

    if (
        importance >= float(a_rules.get("importance_score_min", 75))
        and seo >= float(a_rules.get("seo_value_score_min", 60))
        and knowledge >= float(a_rules.get("knowledge_value_score_min", 70))
        and confidence >= float(a_rules.get("confidence_min", 0.75))
        and risk_score <= float(a_rules.get("risk_score_max", 69))
    ):
        return Decision(
            "A",
            a_rules.get("action", "publish_article"),
            bool(a_rules.get("need_review", True)),
            "a_grade_article",
            "A grade thresholds met",
        )

    if (
        importance >= float(b_rules.get("importance_score_min", 45))
        and knowledge >= float(b_rules.get("knowledge_value_score_min", 40))
        and confidence >= float(b_rules.get("confidence_min", 0.65))
    ):
        return Decision(
            "B",
            b_rules.get("action", "daily_brief_only"),
            bool(b_rules.get("need_review", False)),
            None,
            "B grade thresholds met",
        )

    if confidence >= 0.5 and (entities or topics):
        c_rules = grades.get("C") or {}
        return Decision(
            "C",
            c_rules.get("action", "update_assets_only"),
            bool(c_rules.get("need_review", False)),
            None,
            "Mock C rule: related entity/topic present",
        )

    return Decision("D", d_rules.get("action", "ignore"), bool(d_rules.get("need_review", False)), None, "fallback D")


def insert_decision(conn, event_id: int, decision: Decision) -> None:
    conn.execute(
        """
        INSERT INTO decisions (event_id, action, decision_grade, reason, need_review, status)
        VALUES (?, ?, ?, ?, ?, 'pending')
        """,
        (
            event_id,
            decision.action,
            decision.grade,
            decision.reason,
            1 if decision.need_review else 0,
        ),
    )


def insert_review(conn, event_id: int, review_type: str, reason: str) -> None:
    conn.execute(
        """
        INSERT INTO review_queue (
          target_type, target_id, review_type, reason, status, context_json
        )
        VALUES ('event', ?, ?, ?, 'pending', ?)
        """,
        (
            event_id,
            review_type,
            reason,
            json.dumps({"event_id": event_id}, ensure_ascii=False),
        ),
    )


def write_run(conn, status: str, result: DecisionResult, errors: list[str]) -> None:
    conn.execute(
        """
        INSERT INTO runs (run_type, status, output_json, error_message, finished_at)
        VALUES ('editorial_decision', ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            status,
            json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True),
            "\n".join(errors) if errors else None,
        ),
    )


def make_decisions(
    db_path: Path = DB_PATH,
    config_dir: Path = CONFIG_DIR,
    limit: int | None = None,
    event_id: int | None = None,
    dry_run: bool = False,
) -> DecisionResult:
    db_path = Path(db_path)
    if not dry_run and not db_path.exists():
        raise SystemExit("Database not found. Run: python3 scripts/init_db.py")

    rules = load_rules(config_dir)
    decided_count = 0
    failed_count = 0
    errors: list[str] = []

    with get_conn(db_path) as conn:
        rows = select_events(conn, event_id, limit)
        for row in rows:
            current_event_id = int(row["id"])
            try:
                decision = decide(row, rules)
                decided_count += 1
                if not dry_run:
                    insert_decision(conn, current_event_id, decision)
                    if decision.need_review and decision.review_type:
                        insert_review(conn, current_event_id, decision.review_type, decision.reason)
            except Exception as exc:
                failed_count += 1
                errors.append(f"event_id={current_event_id}: {exc}")

        result = DecisionResult(decided_count, failed_count)
        if not dry_run:
            if failed_count and decided_count == 0:
                status = "failed"
            elif failed_count:
                status = "partial_failed"
            else:
                status = "success"
            write_run(conn, status, result, errors)
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply editorial decision rules to events.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--event-id", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = make_decisions(
        limit=args.limit,
        event_id=args.event_id,
        dry_run=args.dry_run,
    )
    print(
        "[OK] editorial_decision "
        f"decided={result.decided_count} "
        f"failed={result.failed_count}"
    )


if __name__ == "__main__":
    main()
