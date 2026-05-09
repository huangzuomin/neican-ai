#!/usr/bin/env bash
# Clone the neican-ai repo WITHOUT downloading content/images/public.
# Uses sparse-checkout to only fetch skeleton files.
set -euo pipefail

REPO="https://github.com/huangzuomin/neican-ai.git"
BRANCH="main"
DEPLOY_DIR=".deploy"

if [ -d "$DEPLOY_DIR/.git" ]; then
  echo "[deploy-clone] Already cloned, pulling..."
  cd "$DEPLOY_DIR"
  git pull --depth=1 origin "$BRANCH"
  exit 0
fi

rm -rf "$DEPLOY_DIR"
mkdir -p "$DEPLOY_DIR"
cd "$DEPLOY_DIR"

git init
git remote add origin "$REPO"
git sparse-checkout init --cone
# Only check out these directories (no content/ images/ public/ resources/):
git sparse-checkout set layouts static archetypes .gitmodules hugo.toml config.toml

git fetch --depth=1 origin "$BRANCH"
git checkout "$BRANCH"

echo "[deploy-clone] Sparse checkout done."
du -sh .
