from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from sqlite_ops import get_conn


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "neican.sqlite"
SITE_DIR = ROOT / "hugo-site"
TRACKS_PATH = ROOT / "config" / "timeline_tracks.yaml"


@dataclass(frozen=True)
class DailyBriefResult:
    date: str = ""
    events_count: int = 0
    tracks_count: int = 0
    exported: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def json_list(value: str | None) -> list[Any]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except Exception:
        return []
    return parsed if isinstance(parsed, list) else []


def _entity_name(entity: Any) -> str:
    if isinstance(entity, dict):
        return str(entity.get("name") or entity.get("slug") or "")
    return str(entity)


def load_tracks(tracks_path: Path = TRACKS_PATH) -> dict[str, dict[str, Any]]:
    if not tracks_path.exists():
        return {}
    data = yaml.safe_load(tracks_path.read_text(encoding="utf-8")) or {}
    result: dict[str, dict[str, Any]] = {}
    for track in (data.get("tracks") or []) + (data.get("generated_tracks") or []):
        if isinstance(track, dict) and track.get("slug"):
            result[str(track["slug"])] = track
    return result


def frontmatter_block(frontmatter: dict[str, Any], body: str) -> str:
    yaml_text = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False)
    return f"---\n{yaml_text}---\n\n{body.strip()}\n"


def _iso_and_rss_params(date: str) -> tuple[str, str]:
    iso_prefix = f"{date}%"
    try:
        from datetime import datetime as _dt
        target = _dt.strptime(date, "%Y-%m-%d")
        month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        rss_pattern = f"%{target.day:02d} {month_names[target.month-1]} {target.year}%"
    except Exception:
        rss_pattern = "NEVER_MATCH_%"
    return iso_prefix, rss_pattern


def title_normalized(title: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\u4e00-\u9fff]+", " ", title.lower())).strip()


def dedupe_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep one occurrence per event/source/title in a single daily brief."""
    seen_event_ids: set[int] = set()
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    unique: list[dict[str, Any]] = []
    for event in events:
        event_id = int(event.get("event_id") or 0)
        source_url = str(event.get("source_url") or "").strip()
        normalized_title = title_normalized(str(event.get("title") or event.get("source_title") or ""))
        if event_id and event_id in seen_event_ids:
            continue
        if source_url and source_url in seen_urls:
            continue
        if normalized_title and normalized_title in seen_titles:
            continue
        if event_id:
            seen_event_ids.add(event_id)
        if source_url:
            seen_urls.add(source_url)
        if normalized_title:
            seen_titles.add(normalized_title)
        unique.append(event)
    return unique


def fetch_daily_events(conn, date: str) -> list[dict[str, Any]]:
    iso_prefix, rss_pattern = _iso_and_rss_params(date)
    sql = """
        SELECT
          events.id AS event_id, events.event_title, events.event_summary, events.event_type,
          events.event_date, events.entities_json, events.topics_json, events.claims_json,
          decisions.decision_grade, decisions.id AS decision_id,
          raw_items.source_url, raw_items.title AS source_title, sources.name AS source_name,
          timeline_nodes.tracks_json, timeline_nodes.slug AS timeline_slug
        FROM decisions
        JOIN events ON events.id = decisions.event_id
        JOIN raw_items ON raw_items.id = events.raw_item_id
        LEFT JOIN sources ON sources.id = raw_items.source_id
        LEFT JOIN timeline_nodes ON timeline_nodes.event_id = events.id
        WHERE decisions.decision_grade IN ('A', 'B', 'C')
          AND (events.event_date LIKE ? OR events.event_date LIKE ?)
        ORDER BY events.importance_score DESC, events.id
    """
    rows = conn.execute(sql, (iso_prefix, rss_pattern)).fetchall()
    events = []
    for row in rows:
        events.append({
            "event_id": row["event_id"], "title": row["event_title"],
            "summary": row["event_summary"] or "", "type": row["event_type"] or "other",
            "date": (row["event_date"] or "")[:10], "grade": row["decision_grade"],
            "entities": json_list(row["entities_json"]), "topics": json_list(row["topics_json"]),
            "claims": json_list(row["claims_json"]), "tracks": json_list(row["tracks_json"]),
            "source_url": row["source_url"] or "", "source_title": row["source_title"] or row["event_title"],
            "source_name": row["source_name"] or "", "timeline_slug": row["timeline_slug"] or "",
        })
    return dedupe_events(events)


def fetch_track_review_summary(conn, date: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT trd.decision, trd.target_track, trd.proposed_title, trd.reason, trd.confidence, ct.slug AS candidate_slug "
        "FROM track_review_decisions trd JOIN candidate_tracks ct ON ct.id = trd.candidate_track_id "
        "WHERE DATE(trd.created_at) BETWEEN DATE(?, '-1 day') AND DATE(?, '+1 day') ORDER BY trd.id DESC", (date, date),
    ).fetchall()
    return [{"decision": r["decision"], "target_track": r["target_track"], "proposed_title": r["proposed_title"],
             "reason": r["reason"], "candidate_slug": r["candidate_slug"]} for r in rows]


def generate_daily_brief(
    db_path: Path = DB_PATH, site_dir: Path = SITE_DIR, date: str = "", tracks_path: Path = TRACKS_PATH,
) -> DailyBriefResult:
    if not date:
        return DailyBriefResult()
    tracks = load_tracks(tracks_path)
    with get_conn(db_path) as conn:
        events = fetch_daily_events(conn, date)
        track_reviews = fetch_track_review_summary(conn, date)
    if not events:
        return DailyBriefResult(date=date)

    track_events: dict[str, list[dict]] = defaultdict(list)
    untracked: list[dict] = []
    for event in events:
        event_tracks = event.get("tracks") or []
        if event_tracks:
            for ts in event_tracks:
                track_events[ts].append(event)
        else:
            untracked.append(event)

    a_events = [e for e in events if e["grade"] == "A"]
    b_events = [e for e in events if e["grade"] == "B"]
    c_events = [e for e in events if e["grade"] == "C"]

    entity_counter: dict[str, int] = Counter()
    for e in events:
        for ent in e.get("entities", []):
            name = _entity_name(ent)
            if name:
                entity_counter[name] += 1
    top_entities = sorted(entity_counter, key=entity_counter.get, reverse=True)[:5]
    judgment = f"今日共跟踪 {len(events)} 条事件（A级 {len(a_events)}，B级 {len(b_events)}，C级 {len(c_events)}）"
    if top_entities:
        judgment += f"，重点涉及 {'、'.join(top_entities[:3])}。"
    else:
        judgment += "。"

    body = [f"# AI 内参日报：{date}", "", "## 今日关键判断", "", judgment, ""]

    if a_events:
        body += ["## ⭐ A 级事件", ""]
        for e in a_events:
            ens = "、".join(_entity_name(ent) for ent in e["entities"][:3])
            body.append(f"- **{e['title']}** {'(' + ens + ')' if ens else ''}")
            if e["summary"]:
                body.append(f"  {e['summary'][:200]}")
        body.append("")

    if track_events:
        body += ["## 按追踪线组织", ""]
        for ts, tevts in sorted(track_events.items()):
            ti = tracks.get(ts, {})
            tt = ti.get("title", ts)
            body.append(f"### {tt}")
            body.append("")
            for e in tevts:
                body.append(f"- **[{e['grade']}]** {e['title']}")
                if e["summary"]:
                    body.append(f"  {e['summary'][:150]}")
            body.append("")

    if untracked:
        body += ["## 其他事件", ""]
        for e in untracked:
            body.append(f"- **[{e['grade']}]** {e['title']}")
        body.append("")

    if track_reviews:
        body += ["## 追踪线动态", ""]
        for review in track_reviews:
            if review["decision"] == "approved":
                body.append(f"- 🆕 新追踪线「{review['proposed_title']}」已通过审核")
            elif review["decision"] == "merge":
                body.append(f"- 🔄 候选线「{review['proposed_title']}」已并入「{review['target_track']}」")
            elif review["decision"] == "watch":
                body.append(f"- 👀 候选线「{review['proposed_title']}」进入观察")
        body.append("")

    body += ["## 值得继续观察", ""]
    for e in (a_events + b_events)[:5]:
        ens = "、".join(_entity_name(ent) for ent in e["entities"][:2])
        body.append(f"- **{e['title']}** {'(' + ens + ')' if ens else ''} — 观察后续是否带来产品、生态或竞争格局变化")
    body.append("")

    body += ["## 来源索引", ""]
    seen_urls: set[str] = set()
    for e in events:
        if e["source_url"] and e["source_url"] not in seen_urls:
            seen_urls.add(e["source_url"])
            pub = f" · {e['source_name']}" if e["source_name"] else ""
            body.append(f"- [{e['source_title']}]({e['source_url']}){pub}")

    fm = {
        "title": f"AI 内参日报：{date}", "date": f"{date}T18:00:00+08:00", "slug": date,
        "type": "daily_brief", "covered_events": [f"event_{e['event_id']}" for e in events],
        "event_counts": {"A": len(a_events), "B": len(b_events), "C": len(c_events)},
        "tracks_featured": list(track_events.keys()),
        "seo": {"title": f"AI 内参日报 {date}", "description": f"{date} AI 行业关键事件摘要与编辑判断。", "structured_data": "Article", "noindex": False},
        "neican": {"generated_by": "daily_brief_product", "review_status": "draft"},
    }
    content = frontmatter_block(fm, "\n".join(body))
    daily_path = site_dir / "content" / "briefs" / "daily" / f"{date}.md"
    daily_path.parent.mkdir(parents=True, exist_ok=True)
    daily_path.write_text(content, encoding="utf-8")
    return DailyBriefResult(date=date, events_count=len(events), tracks_count=len(track_events), exported=True)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--site", type=Path, default=SITE_DIR)
    parser.add_argument("--tracks", type=Path, default=TRACKS_PATH)
    args = parser.parse_args()
    r = generate_daily_brief(db_path=args.db, site_dir=args.site, date=args.date, tracks_path=args.tracks)
    if r.exported:
        print(f"[OK] daily_brief date={r.date} events={r.events_count} tracks={r.tracks_count}")
    else:
        print(f"[SKIP] daily_brief date={r.date} no events")


if __name__ == "__main__":
    main()
