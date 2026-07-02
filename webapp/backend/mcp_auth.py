"""OAuth 2.1 for the JobRadar MCP server — Phase B (spec: specs/mcp-server.md).

Single-user authorization server, the minimum a remote MCP connector needs:
Dynamic Client Registration + Authorization Code/PKCE + token issue/validate.
The protocol legwork (DCR endpoint, PKCE S256 check, redirect-uri and expiry
validation, 401s on /mcp) is all the MCP SDK's — this module only supplies the
provider (client/code/token storage) and the shared-secret login page that
gates the consent step (it's just you; approval is automatic after login).

Enabled only when BOTH env vars are set (otherwise /mcp stays unauthenticated,
for tailnet-local use):
  JSA_MCP_LOGIN_SECRET  — the one login secret (the Pi's .env, never committed)
  JSA_MCP_ISSUER        — public base URL, e.g. https://dalstonserver.<tailnet>.ts.net

Clients and (sha256-hashed) tokens persist to <JSA_ROOT>/data/mcp_auth.json so
a redeploy doesn't force every connector through the flow again; pending logins
and unredeemed auth codes are in-memory (minutes-lived by design).
"""
from __future__ import annotations

import hashlib
import hmac
import html
import json
import os
import secrets as pysecrets
import sys
import time
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlencode

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
)
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import AnyHttpUrl
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

_BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_BACKEND_DIR.parents[1]))   # repo root -> services.*

from services import store  # noqa: E402

SCOPE = "jobradar"
ACCESS_TOKEN_TTL = 3600
AUTH_CODE_TTL = 300
PENDING_LOGIN_TTL = 600


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class SingleUserOAuthProvider(
    OAuthAuthorizationServerProvider[AuthorizationCode, RefreshToken, AccessToken]
):
    """Every valid token maps to the same (only) user and the same store."""

    def __init__(self, issuer: str, persist_path: Callable[[], Path]):
        self._issuer = issuer.rstrip("/")
        self._persist_path = persist_path            # callable: JSA_ROOT may be set per-test
        self._pending: dict[str, AuthorizationParams] = {}    # login txn -> authorize params
        self._codes: dict[str, AuthorizationCode] = {}        # unredeemed auth codes

    # -- persistence (clients + hashed tokens survive redeploys) ------------------

    def _load(self) -> dict:
        p = self._persist_path()
        if not p.exists():
            return {"clients": {}, "access_tokens": {}, "refresh_tokens": {}}
        return json.loads(p.read_text())

    def _save(self, state: dict) -> None:
        p = self._persist_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        store.atomic_write_text(p, json.dumps(state, indent=1))

    # -- client registration (DCR) -------------------------------------------------

    async def get_client(self, client_id: str) -> Optional[OAuthClientInformationFull]:
        raw = self._load()["clients"].get(client_id)
        return OAuthClientInformationFull.model_validate(raw) if raw else None

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        state = self._load()
        state["clients"][client_info.client_id] = client_info.model_dump(mode="json")
        self._save(state)

    # -- authorize -> login page -> code -------------------------------------------

    async def authorize(self, client: OAuthClientInformationFull,
                        params: AuthorizationParams) -> str:
        txn = pysecrets.token_urlsafe(16)
        self._pending[txn] = params
        self._pending_client = getattr(self, "_pending_client", {})
        self._pending_client[txn] = (client.client_id, time.time())
        return f"{self._issuer}/mcp/login?{urlencode({'txn': txn})}"

    def complete_login(self, txn: str) -> Optional[str]:
        """Called by the login route on a correct secret: mint the auth code and
        return the client redirect URL (None if the txn is unknown/expired)."""
        params = self._pending.pop(txn, None)
        client_id, started = getattr(self, "_pending_client", {}).pop(txn, (None, 0))
        if params is None or time.time() - started > PENDING_LOGIN_TTL:
            return None
        code = AuthorizationCode(
            code=pysecrets.token_urlsafe(32),
            scopes=params.scopes or [SCOPE],
            expires_at=time.time() + AUTH_CODE_TTL,
            client_id=client_id,
            code_challenge=params.code_challenge,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            resource=params.resource,
        )
        self._codes[code.code] = code
        sep = "&" if str(params.redirect_uri).find("?") >= 0 else "?"
        q = {"code": code.code}
        if params.state:
            q["state"] = params.state
        return f"{params.redirect_uri}{sep}{urlencode(q)}"

    async def load_authorization_code(self, client: OAuthClientInformationFull,
                                      authorization_code: str) -> Optional[AuthorizationCode]:
        code = self._codes.get(authorization_code)
        if not code or code.client_id != client.client_id or code.expires_at < time.time():
            return None
        return code

    # -- tokens ---------------------------------------------------------------------

    def _mint(self, client_id: str, scopes: list[str], resource: Optional[str]) -> OAuthToken:
        access, refresh = pysecrets.token_urlsafe(32), pysecrets.token_urlsafe(32)
        now = int(time.time())
        state = self._load()
        state["access_tokens"][_hash(access)] = {
            "client_id": client_id, "scopes": scopes,
            "expires_at": now + ACCESS_TOKEN_TTL, "resource": resource}
        state["refresh_tokens"][_hash(refresh)] = {
            "client_id": client_id, "scopes": scopes}
        self._save(state)
        return OAuthToken(access_token=access, token_type="Bearer",
                          expires_in=ACCESS_TOKEN_TTL, scope=" ".join(scopes),
                          refresh_token=refresh)

    async def exchange_authorization_code(self, client: OAuthClientInformationFull,
                                          authorization_code: AuthorizationCode) -> OAuthToken:
        self._codes.pop(authorization_code.code, None)      # single use
        return self._mint(client.client_id, authorization_code.scopes,
                          authorization_code.resource)

    async def load_refresh_token(self, client: OAuthClientInformationFull,
                                 refresh_token: str) -> Optional[RefreshToken]:
        raw = self._load()["refresh_tokens"].get(_hash(refresh_token))
        if not raw or raw["client_id"] != client.client_id:
            return None
        return RefreshToken(token=refresh_token, client_id=raw["client_id"],
                            scopes=raw["scopes"])

    async def exchange_refresh_token(self, client: OAuthClientInformationFull,
                                     refresh_token: RefreshToken,
                                     scopes: list[str]) -> OAuthToken:
        state = self._load()
        state["refresh_tokens"].pop(_hash(refresh_token.token), None)   # rotate
        self._save(state)
        return self._mint(client.client_id, scopes or refresh_token.scopes, None)

    async def load_access_token(self, token: str) -> Optional[AccessToken]:
        raw = self._load()["access_tokens"].get(_hash(token))
        if not raw:
            return None
        if raw["expires_at"] < time.time():
            state = self._load()
            state["access_tokens"].pop(_hash(token), None)
            self._save(state)
            return None
        return AccessToken(token=token, client_id=raw["client_id"],
                           scopes=raw["scopes"], expires_at=raw["expires_at"],
                           resource=raw.get("resource"))

    async def revoke_token(self, token) -> None:
        state = self._load()
        h = _hash(token.token)
        state["access_tokens"].pop(h, None)
        state["refresh_tokens"].pop(h, None)
        self._save(state)


# --- login page (the consent step; shared secret, auto-approve after) ------------

_LOGIN_FORM = """<!doctype html><title>JobRadar login</title>
<body style="font-family:system-ui;max-width:22rem;margin:15vh auto">
<h3>JobRadar</h3>{error}
<form method="post">
<input type="hidden" name="txn" value="{txn}">
<input type="password" name="secret" placeholder="login secret" autofocus
       style="width:100%;padding:.5rem">
<button style="margin-top:.6rem;padding:.5rem 1.2rem">Authorize</button>
</form></body>"""


def add_login_route(mcp, provider: SingleUserOAuthProvider, login_secret: str) -> None:
    @mcp.custom_route("/mcp/login", methods=["GET", "POST"])
    async def login(request: Request):
        if request.method == "GET":
            txn = request.query_params.get("txn", "")
            return HTMLResponse(_LOGIN_FORM.format(txn=html.escape(txn), error=""))
        form = await request.form()
        txn = str(form.get("txn", ""))
        if not hmac.compare_digest(str(form.get("secret", "")), login_secret):
            return HTMLResponse(_LOGIN_FORM.format(
                txn=html.escape(txn), error="<p style='color:#b00'>wrong secret</p>"),
                status_code=401)
        redirect = provider.complete_login(txn)
        if redirect is None:
            return HTMLResponse("<p>Login expired — restart the connector setup.</p>",
                                status_code=400)
        return RedirectResponse(redirect, status_code=302)


# --- wiring -----------------------------------------------------------------------

def build(issuer: str, login_secret: str,
          persist_path: Optional[Callable[[], Path]] = None):
    """(provider, AuthSettings, secret) for an issuer + login secret."""
    issuer = issuer.rstrip("/")
    provider = SingleUserOAuthProvider(
        issuer, persist_path or (lambda: store.data_dir() / "mcp_auth.json"))
    settings = AuthSettings(
        issuer_url=AnyHttpUrl(issuer),
        resource_server_url=AnyHttpUrl(f"{issuer}/mcp"),
        client_registration_options=ClientRegistrationOptions(
            enabled=True, valid_scopes=[SCOPE], default_scopes=[SCOPE]),
        revocation_options=RevocationOptions(enabled=True),
        required_scopes=[SCOPE],
    )
    return provider, settings, login_secret


def from_env():
    """Auth config from env, or (None, None, "") -> /mcp stays unauthenticated
    (tailnet-local mode)."""
    secret = os.environ.get("JSA_MCP_LOGIN_SECRET", "").strip()
    issuer = os.environ.get("JSA_MCP_ISSUER", "").strip()
    if not (secret and issuer):
        return None, None, ""
    return build(issuer, secret)
