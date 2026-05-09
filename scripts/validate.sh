#!/usr/bin/env bash
set -euo pipefail

echo "Validating OpenClaw project..."

if [ ! -f "AGENTS.md" ]; then
  echo "Missing AGENTS.md"
  exit 1
fi

if [ ! -f "docs/project_spec.md" ]; then
  echo "Missing docs/project_spec.md"
  exit 1
fi

if [ ! -f "docs/openclaw-contract.md" ]; then
  echo "Missing docs/openclaw-contract.md"
  exit 1
fi

if [ -f "openclaw/skill/SKILL.md" ]; then
  echo "Checking Skill package..."

  if ! grep -q "^---" openclaw/skill/SKILL.md; then
    echo "SKILL.md missing YAML frontmatter delimiter"
    exit 1
  fi

  if ! grep -q "^name:" openclaw/skill/SKILL.md; then
    echo "SKILL.md missing name field"
    exit 1
  fi

  if ! grep -q "^description:" openclaw/skill/SKILL.md; then
    echo "SKILL.md missing description field"
    exit 1
  fi
fi

if [ -d "openclaw/agent" ]; then
  echo "Checking agent workspace package..."

  for f in AGENTS.md SOUL.md IDENTITY.md USER.md TOOLS.md; do
    if [ ! -f "openclaw/agent/$f" ]; then
      echo "Missing openclaw/agent/$f"
      exit 1
    fi
  done

  echo "Running agent and release gate tests..."
  pytest openclaw/agent/tests tests
fi

echo "Validation passed."
