"""
Eclipse (EFT Corp) sandbox client — replaces the earlier Absa mock.

*** WHAT'S REAL vs WHAT'S INFERRED, STATED EXPLICITLY ***

REAL, sourced directly from developer.eftcorp.com docs (cited in code
comments below):
  - The login endpoint path and its exact JWT response shape (verified
    against a real sample token published in Eclipse's own "Making your
    First API Call" doc).
  - The existence and paths of the payments, fraud-events, and
    cross-border remittance endpoints.
  - Payment request field NAMES used by Eclipse's API (paymentData, type,
    destinationWalletId, walletId, externalWalletId, cardOnFileId) — these
    are documented in "Payments Use Cases".
  - Absa Bank Limited is a supported bank in Eclipse's sandbox (bank code
    632005), alongside Standard Bank, FNB, Nedbank, Capitec, and others —
    documented in "Sandbox Testing Accounts".

INFERRED / UNVERIFIED — do not present as confirmed without checking:
  - The exact REQUIRED vs optional fields and enum values for `type` in a
    payment request. The docs describe the field names but this build
    never fetched the full request schema or hit the live "Try It"
    console, so the request bodies below are a best-effort shape, not a
    guaranteed-correct payload.
  - The base sandbox URL. Not stated explicitly in the pages this build
    fetched. A sample JWT in Eclipse's own docs has issuer
    "http://eclipse-java-sandbox.ukheshe.rocks" — that's a real clue, not
    a confirmed API host. CONFIRM the actual base URL from Eclipse's
    "Environments & Endpoints" doc or your onboarding email before
    running this against anything real.
  - We do not have onboarded sandbox credentials (identity/password).
    Nothing in this file has been executed against a live Eclipse
    endpoint. What IS verified: the JWT-parsing and request-building
    logic, tested in tests/test_eclipse_client.py against the exact
    sample response JSON published in Eclipse's docs.

Positioning for the pitch: this is the REAL rail integration used for the
demo (PayShap-capable, Absa-capable sandbox). Absa Access remains the
named production target — swapping this client for a direct Absa Access
client later is a contained change, since both are called through the
same PaymentRailClient-shaped interface used in app/api/payments.py.
"""
import os
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx


class EclipseAuthError(Exception):
    pass


class EclipseAPIError(Exception):
    def __init__(self, status_code: int, body: str):
        self.status_code = status_code
        self.body = body
        super().__init__(f"Eclipse API error {status_code}: {body}")


@dataclass
class EclipseToken:
    """Mirrors the EXACT field names in Eclipse's documented login
    response (see "Making your First API Call" in their docs)."""
    header_name: str
    header_value: str  # e.g. "Bearer eyJhbGciOi..."
    session_id: str
    tenant_id: int
    expires: str
    roles: list
    expires_epoch_secs: int

    @classmethod
    def from_api_response(cls, data: dict) -> "EclipseToken":
        return cls(
            header_name=data["headerName"],
            header_value=data["headerValue"],
            session_id=data["sessionId"],
            tenant_id=data["tenantId"],
            expires=data["expires"],
            roles=data.get("roles", []),
            expires_epoch_secs=data["expiresEpochSecs"],
        )

    @property
    def bearer_token(self) -> str:
        # headerValue is documented as "Bearer <jwt>" - strip the prefix
        return self.header_value.split(" ", 1)[1] if " " in self.header_value else self.header_value

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc).timestamp() >= self.expires_epoch_secs


class EclipseClient:
    """
    Sandbox base URL, identity, and password are read from environment
    variables so real credentials are never hardcoded into source:
        ECLIPSE_BASE_URL   (unconfirmed - see module docstring)
        ECLIPSE_IDENTITY
        ECLIPSE_PASSWORD

    If these aren't set, the client raises clearly rather than silently
    falling back to fake behavior - a missing-credentials error is more
    honest than a mock pretending to succeed.
    """

    def __init__(self, base_url: str | None = None, identity: str | None = None,
                 password: str | None = None, timeout: float = 10.0):
        self.base_url = (base_url or os.environ.get("ECLIPSE_BASE_URL", "")).rstrip("/")
        self.identity = identity or os.environ.get("ECLIPSE_IDENTITY")
        self.password = password or os.environ.get("ECLIPSE_PASSWORD")
        self._client = httpx.Client(timeout=timeout)
        self._token: EclipseToken | None = None

    # -- Authentication ----------------------------------------------------
    # Endpoint per Eclipse docs: POST {baseUrl}/eclipse-conductor-rest/v1/authentication/login
    # Documented response fields: headerName, headerValue, sessionId,
    # tenantId, expires, roles, expiresEpochSecs (verified against
    # Eclipse's own published sample token in "Making your First API Call")
    def login(self) -> EclipseToken:
        if not self.identity or not self.password:
            raise EclipseAuthError(
                "ECLIPSE_IDENTITY / ECLIPSE_PASSWORD not set. These are the "
                "sandbox credentials Eclipse provides on onboarding - this "
                "client cannot authenticate without them."
            )
        url = f"{self.base_url}/eclipse-conductor-rest/v1/authentication/login"
        response = self._client.post(url, json={"identity": self.identity, "password": self.password})
        if response.status_code != 200:
            raise EclipseAPIError(response.status_code, response.text)
        self._token = EclipseToken.from_api_response(response.json())
        return self._token

    def _auth_headers(self) -> dict:
        if self._token is None or self._token.is_expired():
            self.login()
        return {self._token.header_name: self._token.header_value}

    # -- Payments ------------------------------------------------------------
    # Endpoint per Eclipse docs: POST {baseUrl}/eclipse-conductor-rest/v1/tenants/{tenantId}/payments
    # Field names (paymentData, type, destinationWalletId, walletId,
    # externalWalletId, externalWalletType, cardOnFileId) are documented in
    # "Payments Use Cases" - exact required/optional shape NOT verified
    # against a live schema in this build. Treat this method's request
    # body as best-effort until checked against the Try It console.
    def initiate_payment(self, tenant_id: int, source_wallet_id: str, amount: float,
                          currency: str, payment_type: str, payment_data: dict) -> dict:
        url = f"{self.base_url}/eclipse-conductor-rest/v1/tenants/{tenant_id}/payments"
        body = {
            "walletId": source_wallet_id,
            "amount": amount,
            "currency": currency,
            "type": payment_type,
            "paymentData": payment_data,
        }
        response = self._client.post(url, json=body, headers=self._auth_headers())
        if response.status_code not in (200, 201):
            raise EclipseAPIError(response.status_code, response.text)
        return response.json()

    # -- Fraud events ----------------------------------------------------------
    # Endpoint per Eclipse docs: POST {baseUrl}/eclipse-conductor-rest/v1/tenants/{tenantId}/fraud-events
    # ("Publish fraud event to third party") - this is a genuinely useful
    # real hook for ThembaPay: when the trust score blocks or flags a
    # transaction, publish that verdict directly into the bank's own
    # fraud-monitoring pipeline rather than only logging it locally.
    def publish_fraud_event(self, tenant_id: int, transaction_reference: str,
                             risk_tier: str, reason: str) -> dict:
        url = f"{self.base_url}/eclipse-conductor-rest/v1/tenants/{tenant_id}/fraud-events"
        body = {
            "transactionReference": transaction_reference,
            "riskTier": risk_tier,
            "reason": reason,
            "source": "ThembaPay",
        }
        response = self._client.post(url, json=body, headers=self._auth_headers())
        if response.status_code not in (200, 201):
            raise EclipseAPIError(response.status_code, response.text)
        return response.json()

    # -- Cross-border remittance -----------------------------------------------
    # Endpoints per Eclipse docs:
    #   POST {baseUrl}/eclipse-conductor-rest/v1/tenants/{tenantId}/remittances/quick-quotes
    #   POST {baseUrl}/eclipse-conductor-rest/v1/tenants/{tenantId}/wallets/{walletId}/remittances
    # This is where ThembaPay's route-optimizer PAPSS/cross-border
    # recommendation would plug into a real settlement rail, instead of
    # the illustrative lookup table in engines/route_optimizer.py.
    def get_remittance_quote(self, tenant_id: int, amount: float, currency: str,
                              destination_country: str) -> dict:
        url = f"{self.base_url}/eclipse-conductor-rest/v1/tenants/{tenant_id}/remittances/quick-quotes"
        body = {"amount": amount, "currency": currency, "destinationCountry": destination_country}
        response = self._client.post(url, json=body, headers=self._auth_headers())
        if response.status_code not in (200, 201):
            raise EclipseAPIError(response.status_code, response.text)
        return response.json()

    def close(self):
        self._client.close()
