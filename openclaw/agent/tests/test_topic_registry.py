import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from topic_registry import normalize_topic_name, sync_topic_registry
from topic_product import generate_topic_pages
from sqlite_ops import get_conn


SCHEMA_SQL = Path(__file__).resolve().parents[1] / "db" / "schema.sql"


def init_temp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "neican.sqlite"
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
    return db_path


def write_taxonomy(tmp_path: Path) -> Path:
    taxonomy_path = tmp_path / "taxonomy.yaml"
    taxonomy_path.write_text(
        yaml.safe_dump(
            {
                "topic_slugs": ["ai-agents", "llm", "ai-policy"],
                "topic_definitions": [
                    {
                        "slug": "ai-agents",
                        "name": "AI Agents",
                        "aliases": ["agentic workflow", "autonomous agents"],
                        "parent": "enterprise-ai",
                        "description": "从会调用工具，到能进入企业流程。",
                    },
                ],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    return taxonomy_path


def test_topic_registry_syncs_taxonomy_to_sqlite(tmp_path):
    db_path = init_temp_db(tmp_path)
    taxonomy_path = write_taxonomy(tmp_path)

    result = sync_topic_registry(db_path=db_path, taxonomy_path=taxonomy_path)
    assert result.synced >= 3  # ai-agents, llm, ai-policy

    with get_conn(db_path) as conn:
        agents = conn.execute(
            "SELECT * FROM topic_registry WHERE slug = 'ai-agents'"
        ).fetchone()
        assert agents is not None
        assert agents["canonical_name"] == "AI Agents"
        aliases = json.loads(agents["aliases_json"])
        assert "agentic workflow" in aliases


def test_topic_registry_normalizes_topic_aliases(tmp_path):
    taxonomy_path = write_taxonomy(tmp_path)
    taxonomy = yaml.safe_load(taxonomy_path.read_text(encoding="utf-8"))

    slug, name = normalize_topic_name("Agentic Workflow", taxonomy)
    assert slug == "ai-agents"
    assert name == "AI Agents"

    slug2, name2 = normalize_topic_name("ai-policy", taxonomy)
    assert slug2 == "ai-policy"
    assert name2 == "AI Policy"  # acronym fix applied
