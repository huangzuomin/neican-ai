from __future__ import annotations

import argparse
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from dotenv import load_dotenv
from openai import OpenAI

from entity_registry import normalize_entity_name
from sqlite_ops import get_conn


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "neican.sqlite"
CONFIG_DIR = ROOT / "config"

# Load .env for LLM access
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class EventModelingResult:
    modeled_count: int = 0
    failed_count: int = 0
    skipped_irrelevant_count: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "failed_count": self.failed_count,
            "modeled_count": self.modeled_count,
            "skipped_irrelevant_count": self.skipped_irrelevant_count,
        }


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"


def contains(text: str, needle: str) -> bool:
    return needle.lower() in text.lower()


def classify_event_type(text: str) -> str:
    rules = [
        ("model_release", ["model", "gpt", "claude", "gemini", "llm"]),
        ("funding", ["funding", "raise", "raised", "series a", "series b"]),
        ("policy", ["policy", "regulation", "监管", "政策"]),
        ("research_paper", ["paper", "research", "arxiv"]),
        ("tool_launch", ["launch", "tool", "推出", "发布工具"]),
        ("safety_issue", ["安全漏洞", "vulnerability", "安全"]),
        ("product_update", ["update", "feature", "release", "announced"]),
    ]
    for event_type, keywords in rules:
        if any(contains(text, keyword) for keyword in keywords):
            return event_type
    return "other"


def match_entities(text: str, aliases: dict[str, list[str]]) -> list[dict[str, str]]:
    entities: list[dict[str, str]] = []
    for name, alias_list in aliases.items():
        candidates = [name, *(alias_list or [])]
        if any(contains(text, candidate) for candidate in candidates):
            entities.append({"name": name, "slug": slugify(name), "type": "company"})
    return entities


def normalize_entities(entities: Any, aliases: dict[str, list[str]]) -> list[dict[str, Any]]:
    """Normalize modeled entities before they are inserted into events."""
    if not isinstance(entities, list):
        return []
    normalized: list[dict[str, Any]] = []
    for entity in entities:
        if isinstance(entity, dict):
            raw_name = str(entity.get("name") or entity.get("slug") or "").strip()
            if not raw_name:
                continue
            slug, canonical = normalize_entity_name(raw_name, aliases)
            item = dict(entity)
            item["name"] = canonical
            item["slug"] = slug
            normalized.append(item)
        else:
            raw_name = str(entity).strip()
            if not raw_name:
                continue
            slug, canonical = normalize_entity_name(raw_name, aliases)
            normalized.append({"name": canonical, "slug": slug, "type": "company"})
    return normalized


def match_topics(text: str, topic_slugs: list[str]) -> list[str]:
    topics: list[str] = []
    for topic in topic_slugs:
        topic_text = topic.replace("-", " ")
        if contains(text, topic) or contains(text, topic_text):
            topics.append(topic)
    return topics


def risk_score(text: str, keywords: list[str]) -> int:
    hits = sum(1 for keyword in keywords if contains(text, keyword))
    return min(hits * 15, 100)


def ai_relevance_score(text: str, rules: dict[str, Any], topic_slugs: list[str]) -> float:
    """Score whether a raw item is directly useful for the AI industry product."""
    if not rules.get("enabled", True):
        return 1.0
    direct_keywords = [str(k) for k in rules.get("direct_keywords", [])]
    context_keywords = [str(k) for k in rules.get("context_keywords", [])] or topic_slugs
    exclusion_keywords = [str(k) for k in rules.get("exclusion_keywords", [])]

    direct_hits = sum(1 for keyword in direct_keywords if contains(text, keyword))
    context_hits = sum(1 for keyword in context_keywords if contains(text, keyword))
    exclusion_hits = sum(1 for keyword in exclusion_keywords if contains(text, keyword))

    if direct_hits:
        score = 0.65 + min(0.35, (direct_hits - 1) * 0.10 + context_hits * 0.10)
    else:
        score = min(1.0, context_hits * 0.18)
    if exclusion_hits and direct_hits == 0:
        score -= min(0.5, exclusion_hits * 0.25)
    return max(0.0, round(score, 2))


def select_raw_items(conn, raw_item_id: int | None, limit: int | None):
    sql = """
        SELECT
          raw_items.id,
          raw_items.title,
          raw_items.clean_text,
          raw_items.published_at,
          COALESCE(sources.trust_level, 3) AS trust_level
        FROM raw_items
        LEFT JOIN sources ON sources.id = raw_items.source_id
        WHERE raw_items.status = 'new'
          AND raw_items.clean_text IS NOT NULL
    """
    params: list[int] = []
    if raw_item_id is not None:
        sql += " AND raw_items.id = ?"
        params.append(raw_item_id)
    sql += " ORDER BY raw_items.id"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    return conn.execute(sql, tuple(params)).fetchall()


def write_run(conn, status: str, result: EventModelingResult, errors: list[str]) -> None:
    conn.execute(
        """
        INSERT INTO runs (run_type, status, output_json, error_message, finished_at)
        VALUES ('event_modeling', ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            status,
            json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True),
            "\n".join(errors) if errors else None,
        ),
    )


# ---------------------------------------------------------------------------
# LLM-backed event modeling
# ---------------------------------------------------------------------------

EVENT_MODELING_SYSTEM = """You are an AI industry event modeling assistant. Analyze news items and extract structured event data.

You MUST respond with a single JSON object matching this schema:
{
  "event_title": "string — concise factual headline",
  "event_summary": "string — 1-3 sentence summary",
  "event_type": "one of: model_release, product_update, company_strategy, research_paper, policy, tool_launch, funding, safety_issue, market_signal, industry_trend, other",
  "entities": [{"name": "string", "slug": "lowercase-hyphenated", "type": "company|model|tool|person|organization", "role": "string — what role does this entity play in the event?"}],
  "topics": ["list of relevant topic slugs from: ai-agents, vibe-coding, rag, mcp, ai-search, embodied-ai, llm, multimodal, ai-safety, ai-policy"],
  "importance_score": "integer 0-100 — how significant for AI industry professionals",
  "seo_value_score": "integer 0-100 — search visibility potential",
  "knowledge_value_score": "integer 0-100 — long-term reference value",
  "risk_score": "integer 0-100 — reputational/legal risk (0 = safe)",
  "confidence": "float 0.0-1.0 — your confidence in this extraction",
  "claims": [{"claim_text": "string — a specific verifiable factual statement extracted from the text", "confidence": "float 0.0-1.0"}],
  "relations": [{"from_entity": "slug", "relation": "string — e.g. released, funded, joined, acquired, partnered_with, competed_with", "to_entity": "slug"}]
}

Rules:
- Extract only facts stated or strongly implied in the text.
- If uncertain, lower confidence rather than guessing.
- risk_score should reflect content sensitivity, not the event's negative impact.
- claims MUST contain actual verifiable statements from the text, NOT empty strings. Each claim should be a specific factual assertion that can be checked. Aim for 2-5 claims per event. Examples: "OpenAI announced GPT-5 will support real-time video reasoning", "Anthropic raised $5B at a $60B valuation", "The regulation draft requires safety assessments for all LLMs with over 10B parameters".
- entities MUST include a role describing their relationship to this event.
- relations capture the key relationships between entities in this event."""


def _get_llm_client() -> tuple[OpenAI, str] | None:
    """Return (client, model) for event modeling, with split-config fallback."""
    api_key = os.getenv("LLM_API_KEY_EVENT") or os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL_EVENT") or os.getenv("LLM_BASE_URL")
    model = os.getenv("LLM_MODEL_EVENT") or os.getenv("LLM_MODEL")
    if not api_key or not base_url or not model:
        return None
    return OpenAI(api_key=api_key, base_url=base_url), model


def llm_model_event(title: str, clean_text: str, client: OpenAI, model: str) -> dict[str, Any] | None:
    """Call LLM to extract structured event data. Returns parsed dict or None."""
    user_content = f"Title: {title}\n\nContent:\n{clean_text[:3000]}"
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": EVENT_MODELING_SYSTEM},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            max_tokens=int(os.getenv("LLM_MAX_TOKENS_EVENT", os.getenv("LLM_MAX_TOKENS", "2048"))),
            temperature=float(os.getenv("LLM_TEMPERATURE_EVENT", os.getenv("LLM_TEMPERATURE", "0.5"))),
            timeout=int(os.getenv("LLM_TIMEOUT_EVENT", os.getenv("LLM_TIMEOUT", "60"))),
        )
        raw = resp.choices[0].message.content or ""
        return json.loads(raw)
    except Exception as exc:
        print(f"  [WARN] LLM call failed: {exc}")
        return None


def _llm_concurrency() -> int:
    try:
        return max(1, int(os.getenv("LLM_CONCURRENCY", "4")))
    except ValueError:
        return 4


def _parallel_llm_results(rows: list[Any], llm: tuple[OpenAI, str] | None) -> dict[int, dict[str, Any] | None]:
    if not llm or not rows:
        return {}
    client, model = llm
    concurrency = min(_llm_concurrency(), len(rows))
    results: dict[int, dict[str, Any] | None] = {}
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_map = {
            executor.submit(
                llm_model_event,
                row["title"] or "Untitled event",
                row["clean_text"] or "",
                client,
                model,
            ): int(row["id"])
            for row in rows
        }
        for future in as_completed(future_map):
            raw_item_id = future_map[future]
            try:
                results[raw_item_id] = future.result()
            except Exception as exc:
                print(f"  [WARN] LLM future failed for raw_item_id={raw_item_id}: {exc}")
                results[raw_item_id] = None
    return results


def _extract_fallback_claims(title: str, clean_text: str) -> list[dict[str, Any]]:
    """Extract simple claims from text using sentence splitting."""
    text = clean_text or title
    if not text:
        return []
    sentences = []
    for s in text.replace("。", ".").replace("！", ".").replace("？", ".").split("."):
        s = s.strip()
        if len(s) > 20 and len(s) < 300:
            sentences.append(s)
    claims = []
    for s in sentences[:5]:
        # Skip generic headers/labels
        if s.startswith("#") or s.startswith("来源"):
            continue
        claims.append({"claim_text": s, "confidence": 0.5})
    return claims


def _fallback_model_event(
    title: str, clean_text: str, row: Any,
    entity_aliases: dict, topic_slugs: list[str], high_risk_keywords: list[str],
) -> dict[str, Any]:
    """Rule-based fallback when LLM is unavailable."""
    combined_text = f"{title}\n{clean_text}"
    entities = match_entities(combined_text, entity_aliases)
    # Add role field to entities
    for e in entities:
        e["role"] = "mentioned"
    return {
        "event_title": title,
        "event_summary": clean_text[:300],
        "event_type": classify_event_type(combined_text),
        "entities": entities,
        "topics": match_topics(combined_text, topic_slugs),
        "importance_score": min(int(row["trust_level"]) * 20, 100),
        "seo_value_score": 60,
        "knowledge_value_score": 55,
        "risk_score": risk_score(combined_text, high_risk_keywords),
        "confidence": 0.60,
        "claims": _extract_fallback_claims(title, clean_text),
        "relations": [],
    }


def model_events(
    db_path: Path = DB_PATH,
    config_dir: Path = CONFIG_DIR,
    mock: bool = False,
    limit: int | None = None,
    raw_item_id: int | None = None,
) -> EventModelingResult:
    db_path = Path(db_path)
    config_dir = Path(config_dir)
    if not db_path.exists():
        raise SystemExit("Database not found. Run: python3 scripts/init_db.py")

    entity_aliases = load_yaml(config_dir / "entity_aliases.yaml")
    taxonomy = load_yaml(config_dir / "taxonomy.yaml")
    risk_rules = load_yaml(config_dir / "risk_rules.yaml")
    editorial_rules = load_yaml(config_dir / "editorial_rules.yaml")
    topic_slugs = taxonomy.get("topic_slugs") or []
    high_risk_keywords = risk_rules.get("high_risk_keywords") or []
    relevance_rules = editorial_rules.get("ai_relevance_gate") or {}
    relevance_threshold = float(relevance_rules.get("threshold", 0.65))

    llm = None if mock else _get_llm_client()
    if llm and not mock:
        print(f"[LLM] Using {llm[1]} for event modeling")
    else:
        print("[FALLBACK] Using rule-based event modeling (mock mode)")

    modeled_count = 0
    failed_count = 0
    skipped_irrelevant_count = 0
    llm_count = 0
    fallback_count = 0
    errors: list[str] = []

    with get_conn(db_path) as conn:
        rows = select_raw_items(conn, raw_item_id, limit)
        llm_results = {} if mock else _parallel_llm_results(list(rows), llm)
        for row in rows:
            raw_item_id_value = int(row["id"])
            try:
                title = row["title"] or "Untitled event"
                clean_text = row["clean_text"] or ""
                combined_text = f"{title}\n{clean_text}"
                relevance = ai_relevance_score(combined_text, relevance_rules, topic_slugs)
                if relevance < relevance_threshold:
                    conn.execute(
                        "UPDATE raw_items SET status = 'ignored', error_message = ? WHERE id = ?",
                        (f"ai_relevance_score={relevance} below threshold={relevance_threshold}", raw_item_id_value),
                    )
                    skipped_irrelevant_count += 1
                    continue

                # Try LLM first, fallback to rules
                modeled: dict[str, Any] | None = llm_results.get(raw_item_id_value)
                if modeled:
                    llm_count += 1

                if not modeled:
                    modeled = _fallback_model_event(
                        title, clean_text, row, entity_aliases, topic_slugs, high_risk_keywords,
                    )
                    fallback_count += 1

                # Normalize and write
                event_title = str(modeled.get("event_title", title))[:500]
                event_summary = str(modeled.get("event_summary", clean_text[:300]))[:1000]
                event_type = str(modeled.get("event_type", "other"))
                entities = normalize_entities(modeled.get("entities", []), entity_aliases)
                topics = modeled.get("topics", [])
                claims = modeled.get("claims", [])
                importance = max(0, min(100, int(modeled.get("importance_score", 50))))
                seo = max(0, min(100, int(modeled.get("seo_value_score", 50))))
                knowledge = max(0, min(100, int(modeled.get("knowledge_value_score", 50))))
                risk = max(0, min(100, int(modeled.get("risk_score", 0))))
                confidence = max(0.0, min(1.0, float(modeled.get("confidence", 0.5))))

                conn.execute(
                    """
                    INSERT INTO events (
                      raw_item_id, event_title, event_summary, event_type, event_date,
                      entities_json, topics_json, claims_json,
                      importance_score, seo_value_score, knowledge_value_score,
                      risk_score, confidence, status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'modeled')
                    """,
                    (
                        raw_item_id_value,
                        event_title,
                        event_summary,
                        event_type,
                        row["published_at"],
                        json.dumps(entities, ensure_ascii=False),
                        json.dumps(topics if isinstance(topics, list) else [], ensure_ascii=False),
                        json.dumps(claims if isinstance(claims, list) else [], ensure_ascii=False),
                        importance,
                        seo,
                        knowledge,
                        risk,
                        confidence,
                    ),
                )
                conn.execute(
                    "UPDATE raw_items SET status = 'processed' WHERE id = ?",
                    (raw_item_id_value,),
                )
                modeled_count += 1
            except Exception as exc:
                failed_count += 1
                errors.append(f"raw_item_id={raw_item_id_value}: {exc}")

        result = EventModelingResult(modeled_count, failed_count, skipped_irrelevant_count)
        if failed_count and modeled_count == 0:
            status = "failed"
        elif failed_count:
            status = "partial_failed"
        else:
            status = "success"

        # Log mode used
        extra = {"llm_count": llm_count, "fallback_count": fallback_count}
        run_output = {**result.to_dict(), **extra}
        conn.execute(
            """
            INSERT INTO runs (run_type, status, output_json, error_message, finished_at)
            VALUES ('event_modeling', ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                status,
                json.dumps(run_output, ensure_ascii=False, sort_keys=True),
                "\n".join(errors) if errors else None,
            ),
        )
        print(f"  LLM: {llm_count}, Fallback: {fallback_count}")
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Model raw_items into events (LLM + rule fallback).")
    parser.add_argument("--mock", action="store_true", help="Force rule-based fallback (no LLM)")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--raw-item-id", type=int, default=None)
    args = parser.parse_args()

    result = model_events(
        mock=args.mock,
        limit=args.limit,
        raw_item_id=args.raw_item_id,
    )
    print(
        "[OK] event_modeling "
        f"modeled={result.modeled_count} "
        f"failed={result.failed_count}"
    )


if __name__ == "__main__":
    main()
