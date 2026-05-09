from __future__ import annotations

import hashlib


def compute_content_hash(title: str | None, source_url: str | None, published_at: str | None) -> str:
    content = "".join((title or "", source_url or "", published_at or ""))
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
