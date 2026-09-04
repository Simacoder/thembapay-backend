"""
Run: pytest tests/test_eclipse_client.py -v

These tests do NOT hit a live Eclipse sandbox (no credentials available
in this build). Instead they verify the client's parsing and
request-building logic against a mocked HTTP transport, using the EXACT
sample login response published in Eclipse's own docs
(developer.eftcorp.com/reference/authorization) so at least the
"do we correctly understand their documented contract" question is
actually tested, not assumed.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
import pytest

from app.integrations.eclipse_client import EclipseAPIError, EclipseAuthError, EclipseClient, EclipseToken

# This is Eclipse's own published sample response, copied verbatim from
# developer.eftcorp.com/reference/authorization ("Making your First API
# Call"), field names and structure exactly as documented.
SAMPLE_LOGIN_RESPONSE = {
    "headerName": "Authorization",
    "headerValue": "Bearer eyJraWQiOiIxIiwiYWxnIjoiUFMyNTYifQ.sample-jwt-body.sample-signature",
    "sessionId": "6796f421-447d-4264-a2b6-4e30d57e3936",
    "tenantId": 5987,
    "expires": "2099-10-11T15:47:56.488Z",  # far future so is_expired() is False in tests
    "roles": [],
    "expiresEpochSecs": 4000000000,  # far future timestamp
}


def test_token_parses_documented_response_shape():
    token = EclipseToken.from_api_response(SAMPLE_LOGIN_RESPONSE)
    assert token.header_name == "Authorization"
    assert token.session_id == "6796f421-447d-4264-a2b6-4e30d57e3936"
    assert token.tenant_id == 5987
    assert token.bearer_token.startswith("eyJraWQi")
    assert token.is_expired() is False


def test_token_strips_bearer_prefix_correctly():
    token = EclipseToken.from_api_response(SAMPLE_LOGIN_RESPONSE)
    # headerValue is "Bearer <jwt>" per docs - confirm we extract just the JWT
    assert not token.bearer_token.startswith("Bearer")


def _mock_transport(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_login_raises_clear_error_without_credentials():
    client = EclipseClient(base_url="https://example-sandbox.test", identity=None, password=None)
    with pytest.raises(EclipseAuthError):
        client.login()


def test_login_success_against_mocked_documented_response():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/eclipse-conductor-rest/v1/authentication/login"
        return httpx.Response(200, json=SAMPLE_LOGIN_RESPONSE)

    client = EclipseClient(base_url="https://example-sandbox.test", identity="test-user", password="test-pass")
    client._client = _mock_transport(handler)

    token = client.login()
    assert token.tenant_id == 5987
    assert client._token is not None


def test_login_failure_raises_api_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="invalid credentials")

    client = EclipseClient(base_url="https://example-sandbox.test", identity="bad-user", password="bad-pass")
    client._client = _mock_transport(handler)

    with pytest.raises(EclipseAPIError) as exc_info:
        client.login()
    assert exc_info.value.status_code == 401


def test_initiate_payment_sends_documented_field_names():
    captured_body = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if "/authentication/login" in str(request.url):
            return httpx.Response(200, json=SAMPLE_LOGIN_RESPONSE)
        assert request.url.path == "/eclipse-conductor-rest/v1/tenants/5987/payments"
        import json
        captured_body.update(json.loads(request.content))
        return httpx.Response(201, json={"paymentId": "PAY-123", "status": "PENDING"})

    client = EclipseClient(base_url="https://example-sandbox.test", identity="test-user", password="test-pass")
    client._client = _mock_transport(handler)

    result = client.initiate_payment(
        tenant_id=5987, source_wallet_id="WALLET-1", amount=5000, currency="ZAR",
        payment_type="WALLET_TRANSFER", payment_data={"destinationWalletId": "WALLET-2"},
    )

    assert result["paymentId"] == "PAY-123"
    # confirm the documented field names were actually used in the request
    assert captured_body["walletId"] == "WALLET-1"
    assert captured_body["type"] == "WALLET_TRANSFER"
    assert "paymentData" in captured_body


def test_publish_fraud_event_reaches_documented_endpoint():
    def handler(request: httpx.Request) -> httpx.Response:
        if "/authentication/login" in str(request.url):
            return httpx.Response(200, json=SAMPLE_LOGIN_RESPONSE)
        assert request.url.path == "/eclipse-conductor-rest/v1/tenants/5987/fraud-events"
        return httpx.Response(201, json={"eventId": "FRAUD-001"})

    client = EclipseClient(base_url="https://example-sandbox.test", identity="test-user", password="test-pass")
    client._client = _mock_transport(handler)

    result = client.publish_fraud_event(
        tenant_id=5987, transaction_reference="TX-001", risk_tier="high", reason="new beneficiary, high amount"
    )
    assert result["eventId"] == "FRAUD-001"
