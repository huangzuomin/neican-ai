#!/usr/bin/env bash
set -euo pipefail

HUGO_VERSION="${HUGO_VERSION:-0.148.2}"
HUGO_BIN="/tmp/hugo"

if [ ! -x "$HUGO_BIN" ]; then
  curl -fsSL "https://github.com/gohugoio/hugo/releases/download/v${HUGO_VERSION}/hugo_extended_${HUGO_VERSION}_linux-amd64.tar.gz" -o /tmp/hugo.tar.gz
  tar -xzf /tmp/hugo.tar.gz -C /tmp hugo
fi

"$HUGO_BIN" version
"$HUGO_BIN" --destination "$(pwd)/public" --gc --minify --cleanDestinationDir

test -s public/index.html
