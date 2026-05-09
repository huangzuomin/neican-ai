import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_hugo import BuildResult, build_hugo, find_broken_internal_links
from sqlite_ops import get_conn


SCHEMA_SQL = ROOT / "db" / "schema.sql"


def init_temp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "neican.sqlite"
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
    return db_path


def test_build_hugo_success_writes_run(tmp_path, monkeypatch):
    db_path = init_temp_db(tmp_path)
    site_dir = tmp_path / "hugo-site"
    site_dir.mkdir()
    logs_dir = tmp_path / "logs" / "build"

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout="built", stderr="")

    monkeypatch.setattr("build_hugo.subprocess.run", fake_run)

    result = build_hugo(site_dir=site_dir, db_path=db_path, logs_dir=logs_dir)

    assert result == BuildResult(success=True, log_path=None)
    with get_conn(db_path) as conn:
        run = conn.execute("SELECT status, output_json FROM runs WHERE run_type='hugo_build'").fetchone()
    assert run["status"] == "success"
    assert json.loads(run["output_json"]) == {"log_path": None, "success": True}
    assert not logs_dir.exists()


def test_build_hugo_failure_writes_log_and_run(tmp_path, monkeypatch):
    db_path = init_temp_db(tmp_path)
    site_dir = tmp_path / "hugo-site"
    site_dir.mkdir()
    logs_dir = tmp_path / "logs" / "build"

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 1, stdout="partial", stderr="boom")

    monkeypatch.setattr("build_hugo.subprocess.run", fake_run)

    result = build_hugo(site_dir=site_dir, db_path=db_path, logs_dir=logs_dir)

    assert result.success is False
    assert result.log_path is not None
    assert Path(result.log_path).exists()
    assert "partial" in Path(result.log_path).read_text(encoding="utf-8")
    assert "boom" in Path(result.log_path).read_text(encoding="utf-8")
    with get_conn(db_path) as conn:
        run = conn.execute("SELECT status, output_json FROM runs WHERE run_type='hugo_build'").fetchone()
    assert run["status"] == "failed"
    assert json.loads(run["output_json"])["success"] is False


def test_build_hugo_missing_binary_writes_log(tmp_path, monkeypatch):
    db_path = init_temp_db(tmp_path)
    site_dir = tmp_path / "hugo-site"
    site_dir.mkdir()
    logs_dir = tmp_path / "logs" / "build"

    def fake_run(*args, **kwargs):
        raise FileNotFoundError("hugo")

    monkeypatch.setattr("build_hugo.subprocess.run", fake_run)

    result = build_hugo(site_dir=site_dir, db_path=db_path, logs_dir=logs_dir)

    assert result.success is False
    assert result.log_path is not None
    assert "hugo executable not found" in Path(result.log_path).read_text(encoding="utf-8")


def test_find_broken_internal_links_reports_missing_targets(tmp_path):
    public = tmp_path / "public"
    (public / "exists").mkdir(parents=True)
    (public / "exists" / "index.html").write_text("ok", encoding="utf-8")
    (public / "index.html").write_text(
        '<a href="/exists/">ok</a><a href="/missing/">missing</a><a href="https://example.com">external</a>',
        encoding="utf-8",
    )

    assert find_broken_internal_links(public) == ["index.html -> /missing/"]


def test_build_hugo_blocks_broken_internal_links(tmp_path, monkeypatch):
    db_path = init_temp_db(tmp_path)
    site_dir = tmp_path / "hugo-site"
    public = site_dir / "public"
    public.mkdir(parents=True)
    (public / "index.html").write_text('<a href="/missing/">missing</a>', encoding="utf-8")
    logs_dir = tmp_path / "logs" / "build"

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout="built", stderr="")

    monkeypatch.setattr("build_hugo.subprocess.run", fake_run)

    result = build_hugo(site_dir=site_dir, db_path=db_path, logs_dir=logs_dir)

    assert result.success is False
    assert result.log_path is not None
    assert "index.html -> /missing/" in Path(result.log_path).read_text(encoding="utf-8")
