from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from app.core.config import Settings, _parse_cors_origins


PREVIEW_ORIGIN = "https://p2-34-preview.vercel.app"


def _settings(environment: str, origins: str = "") -> Settings:
    return Settings(
        app_environment=environment,
        CORS_ALLOWED_ORIGINS=origins,
        _env_file=None,
    )


def _cors_client(configured: Settings) -> TestClient:
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=configured.allowed_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return TestClient(app)


def test_origin_parser_trims_ignores_empty_normalizes_and_deduplicates() -> None:
    assert _parse_cors_origins(f" {PREVIEW_ORIGIN}/, ,{PREVIEW_ORIGIN} ") == [PREVIEW_ORIGIN]


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "javascript:alert(1)",
        "kaiqiang.ai",
        "https://example.com/path",
        "https://example.com?query=yes",
        "https://example.com/#fragment",
    ],
)
def test_origin_parser_rejects_invalid_origins(origin: str) -> None:
    with pytest.raises(ValueError):
        _parse_cors_origins(origin)


def test_origin_parser_allows_localhost_with_port() -> None:
    assert _parse_cors_origins("http://localhost:3000") == ["http://localhost:3000"]


def test_production_has_only_production_defaults_and_explicit_origins() -> None:
    extra = "https://admin.kaiqiang.ai"
    origins = _settings("production", extra).allowed_origins
    assert origins == ["https://kaiqiang.ai", "https://www.kaiqiang.ai", extra]
    assert not any(origin.endswith(".vercel.app") for origin in origins)
    assert "http://localhost:3000" not in origins


def test_preview_has_only_explicit_origins() -> None:
    origins = _settings("preview", PREVIEW_ORIGIN).allowed_origins
    assert origins == [PREVIEW_ORIGIN]
    assert "https://kaiqiang.ai" not in origins
    assert "https://www.kaiqiang.ai" not in origins


def test_preview_without_origins_fails_configuration() -> None:
    with pytest.raises(ValidationError, match="CORS_ALLOWED_ORIGINS must be configured for preview"):
        _settings("preview")


@pytest.mark.parametrize("environment", ["development", "test"])
def test_local_environments_include_localhost_and_explicit_origins(environment: str) -> None:
    extra = "https://local-tunnel.example.com"
    assert _settings(environment, extra).allowed_origins == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        extra,
    ]


def test_legacy_cors_origins_environment_alias_remains_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", PREVIEW_ORIGIN)
    configured = Settings(app_environment="preview", _env_file=None)
    assert configured.allowed_origins == [PREVIEW_ORIGIN]


def test_allowed_preview_origin_receives_cors_header() -> None:
    response = _cors_client(_settings("preview", PREVIEW_ORIGIN)).get(
        "/health",
        headers={"Origin": PREVIEW_ORIGIN},
    )
    assert response.headers["access-control-allow-origin"] == PREVIEW_ORIGIN
    assert "access-control-allow-credentials" not in response.headers


@pytest.mark.parametrize("origin", ["https://kaiqiang.ai", "https://unknown.example.com"])
def test_disallowed_origin_receives_no_cors_header(origin: str) -> None:
    response = _cors_client(_settings("preview", PREVIEW_ORIGIN)).get(
        "/health",
        headers={"Origin": origin},
    )
    assert "access-control-allow-origin" not in response.headers
    assert "access-control-allow-credentials" not in response.headers
