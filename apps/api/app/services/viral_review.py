from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from app.core.config import settings


def _canonical(context: dict[str, Any]) -> bytes:
    return json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def create_review_token(context: dict[str, Any]) -> str:
    secret = settings.viral_review_signing_secret
    if not secret:
        return ""
    return hmac.new(secret.encode("utf-8"), _canonical(context), hashlib.sha256).hexdigest()


def verify_review_token(context: dict[str, Any], token: str) -> bool:
    expected = create_review_token(context)
    return bool(expected and token and hmac.compare_digest(expected, token))
