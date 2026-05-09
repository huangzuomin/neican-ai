from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from sqlite_ops import get_conn


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "neican.sqlite"
SITE_DIR = ROOT / "hugo-site"
PUBLISH_DIR = ROOT / "hugo-site" / "public"
LOGS_DIR = ROOT / "logs" / "publish"

DEPLOY_REPO = os.getenv("DEPLOY_REPO", "huangzuomin/neican-ai")
DEPLOY_BRANCH = os.getenv("DEPLOY_BRANCH", "main")


@dataclass(frozen=True)
class DeployResult:
    success: bool
    commit_sha: str = ""
    files_changed: int = 0
    message: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _collect_files(directory: Path, max_bytes: int = 10 * 1024 * 1024) -> list[dict]:
    """Walk directory and return [{path, content_b64, size}] for all files under max_bytes."""
    files = []
    for fpath in sorted(directory.rglob("*")):
        if not fpath.is_file():
            continue
        rel = fpath.relative_to(directory)
        # Skip lock files
        if rel.name == ".hugo_build.lock":
            continue
        size = fpath.stat().st_size
        if size > max_bytes:
            continue
        content = base64.b64encode(fpath.read_bytes()).decode("ascii")
        files.append({
            "path": str(rel),
            "content": content,
            "size": size,
        })
    return files


def _tree_suffix(files: list[dict]) -> str:
    """Return a short hash-like suffix from file list for dedup detection."""
    import hashlib
    h = hashlib.md5()
    for f in files:
        h.update(f["path"].encode())
    return h.hexdigest()[:8]


def deploy_api(
    db_path: Path = DB_PATH,
    site_dir: Path = SITE_DIR,
    deploy_repo: str = DEPLOY_REPO,
    deploy_branch: str = DEPLOY_BRANCH,
    dry_run: bool = False,
    message: str | None = None,
) -> DeployResult:
    from build_hugo import build_hugo

    # Step 1: Hugo build
    build_result = build_hugo(site_dir=site_dir, db_path=db_path)
    if not build_result.success:
        return DeployResult(False, message="Hugo build failed")

    public_dir = site_dir / "public"
    if not public_dir.exists():
        return DeployResult(False, message="public/ not found after build")

    # Step 2: Collect files
    files = _collect_files(public_dir)
    if not files:
        return DeployResult(True, message="No files to deploy")

    total_size = sum(f["size"] for f in files)
    commit_msg = message or f"deploy: {datetime.now().strftime('%Y-%m-%d %H:%M')} — {len(files)} files ({total_size // 1024}KB)"

    if dry_run:
        print(f"[DRY RUN] {len(files)} files, {total_size // 1024}KB total")
        # Show some sample paths
        for f in files[:10]:
            print(f"  {f['path']} ({f['size']}B)")
        if len(files) > 10:
            print(f"  ... and {len(files) - 10} more")
        return DeployResult(True, files_changed=len(files), message=f"[DRY RUN] {commit_msg}")

    # Step 3: Get current HEAD SHA
    try:
        ref_result = subprocess.run(
            ["gh", "api", f"repos/{deploy_repo}/git/ref/heads/{deploy_branch}"],
            capture_output=True, text=True, timeout=30,
        )
        if ref_result.returncode != 0:
            return DeployResult(False, message=f"Failed to get ref: {ref_result.stderr.strip()}")
        head_sha = json.loads(ref_result.stdout)["object"]["sha"]
    except Exception as exc:
        return DeployResult(False, message=f"gh api ref failed: {exc}")

    # Step 4: Get current tree SHA from HEAD commit
    try:
        commit_result = subprocess.run(
            ["gh", "api", f"repos/{deploy_repo}/git/commits/{head_sha}"],
            capture_output=True, text=True, timeout=30,
        )
        tree_sha = json.loads(commit_result.stdout)["tree"]["sha"]
    except Exception as exc:
        return DeployResult(False, message=f"Failed to get tree: {exc}")

    # Step 5: Create blobs and build tree entries
    print(f"Creating {len(files)} blobs...")
    tree_entries = []
    batch_size = 50
    for i in range(0, len(files), batch_size):
        batch = files[i:i + batch_size]
        for f in batch:
            try:
                blob_result = subprocess.run(
                    ["gh", "api", f"repos/{deploy_repo}/git/blobs",
                     "-f", f"content={f['content']}",
                     "-f", "encoding=base64"],
                    capture_output=True, text=True, timeout=30,
                )
                if blob_result.returncode != 0:
                    print(f"  [WARN] blob failed for {f['path']}: {blob_result.stderr.strip()}")
                    continue
                blob_sha = json.loads(blob_result.stdout)["sha"]
                # Determine if file is executable
                mode = "100755" if f["path"].endswith(".sh") else "100644"
                tree_entries.append({
                    "path": f["path"],
                    "mode": mode,
                    "type": "blob",
                    "sha": blob_sha,
                })
            except Exception as exc:
                print(f"  [WARN] blob error for {f['path']}: {exc}")
                continue
        print(f"  {min(i + batch_size, len(files))}/{len(files)} blobs created")

    if not tree_entries:
        return DeployResult(False, message="No blobs created successfully")

    # Step 6: Create tree
    print(f"Creating tree with {len(tree_entries)} entries...")
    tree_input = {"base_tree": tree_sha, "tree": tree_entries}
    try:
        tree_result = subprocess.run(
            ["gh", "api", f"repos/{deploy_repo}/git/trees",
             "--input", "-"],
            input=json.dumps(tree_input),
            capture_output=True, text=True, timeout=60,
        )
        if tree_result.returncode != 0:
            return DeployResult(False, message=f"Tree creation failed: {tree_result.stderr.strip()}")
        new_tree_sha = json.loads(tree_result.stdout)["sha"]
    except Exception as exc:
        return DeployResult(False, message=f"Tree creation error: {exc}")

    # Step 7: Create commit
    try:
        commit_input = {
            "message": commit_msg,
            "tree": new_tree_sha,
            "parents": [head_sha],
        }
        commit_result = subprocess.run(
            ["gh", "api", f"repos/{deploy_repo}/git/commits",
             "-f", f"message={commit_msg}",
             "-f", f"tree={new_tree_sha}",
             "-f", f"parents[]={head_sha}"],
            capture_output=True, text=True, timeout=30,
        )
        if commit_result.returncode != 0:
            return DeployResult(False, message=f"Commit failed: {commit_result.stderr.strip()}")
        new_commit_sha = json.loads(commit_result.stdout)["sha"]
    except Exception as exc:
        return DeployResult(False, message=f"Commit error: {exc}")

    # Step 8: Update ref
    print(f"Pushing to {deploy_repo}:{deploy_branch}...")
    try:
        ref_result = subprocess.run(
            ["gh", "api", "-X", "PATCH", f"repos/{deploy_repo}/git/refs/heads/{deploy_branch}",
             "--input", "-"],
            input=json.dumps({"sha": new_commit_sha, "force": True}),
            capture_output=True, text=True, timeout=30,
        )
        if ref_result.returncode != 0:
            return DeployResult(False, commit_sha=new_commit_sha[:12],
                                message=f"Ref update failed: {ref_result.stderr.strip()}")
    except Exception as exc:
        return DeployResult(False, commit_sha=new_commit_sha[:12], message=f"Ref update error: {exc}")

    commit_short = new_commit_sha[:12]

    # Step 9: Write publish log
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    log_path.write_text(json.dumps({
        "commit": commit_short,
        "files_changed": len(tree_entries),
        "deployed_at": datetime.now().isoformat(),
        "deploy_repo": deploy_repo,
        "deploy_branch": deploy_branch,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # Step 10: Write run record
    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO runs (run_type, status, output_json, finished_at)
            VALUES ('deploy', 'success', ?, CURRENT_TIMESTAMP)
            """,
            (json.dumps({"commit": commit_short, "files_changed": len(tree_entries)}, ensure_ascii=False),),
        )

    return DeployResult(True, commit_sha=commit_short,
                        files_changed=len(tree_entries), message="Deployed via GitHub API")


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy neican.ai to GitHub (no clone needed)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deployed")
    parser.add_argument("--message", default=None, help="Custom commit message")
    parser.add_argument("--repo", default=DEPLOY_REPO, help="GitHub repo (owner/name)")
    parser.add_argument("--branch", default=DEPLOY_BRANCH, help="Branch name")
    args = parser.parse_args()

    result = deploy_api(
        dry_run=args.dry_run,
        message=args.message,
        deploy_repo=args.repo,
        deploy_branch=args.branch,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    if not result.success:
        sys.exit(1)


if __name__ == "__main__":
    main()
