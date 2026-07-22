from __future__ import annotations

from contextvars import ContextVar, Token
from uuid import uuid4


_request_id: ContextVar[str] = ContextVar("viral_request_id", default="")


def new_request_id() -> str:
    return f"viral_{uuid4().hex[:16]}"


def bind_request_id(request_id: str) -> Token[str]:
    return _request_id.set(request_id)


def reset_request_id(token: Token[str]) -> None:
    _request_id.reset(token)


def current_request_id() -> str:
    return _request_id.get()
