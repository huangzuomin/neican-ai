#!/usr/bin/env bash
set -euo pipefail

AGENT_NAME="${AGENT_NAME:-neican-editor}"
SOURCE_DIR="openclaw/agent"
TARGET_DIR="${OPENCLAW_AGENT_WORKSPACE:-$HOME/.openclaw/workspace-${AGENT_NAME}}"
RSYNC_EXCLUDES=(
  "--exclude=.pytest_cache/"
  "--exclude=__pycache__/"
  "--exclude=*.log"
  "--exclude=logs/"
  "--exclude=*.sqlite-shm"
  "--exclude=*.sqlite-wal"
  "--exclude=hugo-site/public/"
  "--exclude=hugo-site/resources/"
  "--exclude=.hugo_build.lock"
)

if [ -z "$AGENT_NAME" ]; then
  echo "Please set AGENT_NAME or edit scripts/deploy-agent.sh before deployment."
  echo "Example: AGENT_NAME=neican-editor bash scripts/deploy-agent.sh"
  exit 1
fi

if [ ! -f "${SOURCE_DIR}/AGENTS.md" ]; then
  echo "Missing ${SOURCE_DIR}/AGENTS.md"
  exit 1
fi

echo "Deploying agent workspace to: ${TARGET_DIR}"

if [ -d "${TARGET_DIR}" ] && [ -n "$(ls -A "${TARGET_DIR}" 2>/dev/null)" ]; then
  BACKUP_DIR="${TARGET_DIR}.backup.$(date +%Y%m%d%H%M%S)"
  echo "Existing target found. Creating backup: ${BACKUP_DIR}"
  cp -a "${TARGET_DIR}" "${BACKUP_DIR}"
fi

mkdir -p "${TARGET_DIR}"
rsync -av --delete "${RSYNC_EXCLUDES[@]}" "${SOURCE_DIR}/" "${TARGET_DIR}/"

echo "Agent workspace deployed."
echo "Next: run the Manual Runtime Test Command from docs/openclaw-contract.md"
