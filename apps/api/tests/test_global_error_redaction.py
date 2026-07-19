from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app import main


class ValidationPayload(BaseModel):
    count: int = Field(..., ge=1)


def _client() -> TestClient:
    app = FastAPI()
    app.add_exception_handler(Exception, main.unhandled_exception_handler)

    @app.get("/ordinary-error")
    def ordinary_error():
        raise RuntimeError("internal file /app/private/provider.py")

    @app.get("/sensitive-error")
    def sensitive_error():
        raise Exception("supabase service key abc123 database password hidden")

    @app.get("/business-error")
    def business_error():
        raise HTTPException(
            status_code=409,
            detail={"code": "business_rule", "message": "Stable business response."},
        )

    @app.post("/validation")
    def validation(payload: ValidationPayload):
        return payload

    return TestClient(app, raise_server_exceptions=False)


def test_unhandled_exception_returns_stable_redacted_500(monkeypatch):
    logged: list[tuple] = []
    monkeypatch.setattr(main.logger, "exception", lambda *args: logged.append(args))

    response = _client().get("/ordinary-error")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    response_text = response.text.lower()
    for internal_detail in ("runtimeerror", "provider.py", "traceback", "/app/private"):
        assert internal_detail not in response_text
    assert logged == [("Unhandled API exception on %s %s", "GET", "/ordinary-error")]


def test_sensitive_exception_value_is_not_returned():
    response = _client().get("/sensitive-error")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    for secret in ("abc123", "supabase service key", "database password"):
        assert secret not in response.text.lower()


def test_http_exception_contract_is_unchanged():
    response = _client().get("/business-error")

    assert response.status_code == 409
    assert response.json() == {
        "detail": {"code": "business_rule", "message": "Stable business response."}
    }


def test_request_validation_keeps_fastapi_422_contract():
    response = _client().post("/validation", json={"count": 0})

    assert response.status_code == 422
    payload = response.json()
    assert isinstance(payload.get("detail"), list)
    assert payload["detail"][0]["loc"] == ["body", "count"]
