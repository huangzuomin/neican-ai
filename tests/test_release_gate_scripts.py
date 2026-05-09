from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_deploy_agent_excludes_generated_and_runtime_state() -> None:
    script = (ROOT / "scripts" / "deploy-agent.sh").read_text(encoding="utf-8")

    required_excludes = [
        ".pytest_cache/",
        "__pycache__/",
        "*.log",
        "logs/",
        "*.sqlite-shm",
        "*.sqlite-wal",
        "hugo-site/public/",
        "hugo-site/resources/",
        ".hugo_build.lock",
    ]

    for pattern in required_excludes:
        assert f"--exclude={pattern}" in script


def test_validate_runs_agent_pytest_suite() -> None:
    script = (ROOT / "scripts" / "validate.sh").read_text(encoding="utf-8")

    assert "pytest openclaw/agent/tests tests" in script


def test_deploy_manifest_lists_script_exclusions() -> None:
    manifest = (ROOT / "docs" / "deploy_manifest.md").read_text(encoding="utf-8")

    required_never_deploy = [
        ".pytest_cache/",
        "logs/",
        "__pycache__/",
        "*.log",
        "*.sqlite-shm",
        "*.sqlite-wal",
        "hugo-site/public/",
        "hugo-site/resources/",
        ".hugo_build.lock",
    ]

    for pattern in required_never_deploy:
        assert pattern in manifest
