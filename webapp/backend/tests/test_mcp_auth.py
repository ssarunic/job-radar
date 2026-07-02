"""OAuth 2.1 on /mcp (Phase B) — full connector flow, network-free.

Drives the real HTTP surface the way Claude's connector does: DCR ->
/authorize -> shared-secret login -> code+PKCE -> /token -> Bearer call.
Built on a dedicated auth-enabled instance from mcp_app.create_mcp(); the
module-default instance (no env set) stays unauthenticated — pinned here too.
"""
import base64
import hashlib
import json
import secrets
from urllib.parse import parse_qs, urlparse

import anyio
import mcp_app
import mcp_auth
import pytest
from starlette.testclient import TestClient

SECRET = "hunter2"
REDIRECT = "http://localhost:33418/callback"
MCP_HEADERS = {"Content-Type": "application/json",
               "Accept": "application/json, text/event-stream"}
INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                   "clientInfo": {"name": "t", "version": "0"}}}


@pytest.fixture
def auth_setup(tmp_path, monkeypatch):
    monkeypatch.setenv("JSA_ROOT", str(tmp_path))
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "jobs.jsonl").write_text("")
    persist = tmp_path / "data" / "mcp_auth.json"
    provider, settings, secret = mcp_auth.build(
        "http://localhost", SECRET, persist_path=lambda: persist)
    server = mcp_app.create_mcp(provider, settings, secret)
    with TestClient(server.streamable_http_app()) as client:
        yield client, provider, persist


def _pkce():
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


def _register(client) -> dict:
    r = client.post("/register", json={
        "client_name": "claude", "redirect_uris": [REDIRECT],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"], "token_endpoint_auth_method": "client_secret_post"})
    assert r.status_code == 201, r.text
    return r.json()


def _authorize(client, reg, challenge, login_secret=SECRET) -> str:
    """/authorize -> login page -> POST secret -> auth code."""
    r = client.get("/authorize", params={
        "response_type": "code", "client_id": reg["client_id"],
        "redirect_uri": REDIRECT, "state": "st4te",
        "code_challenge": challenge, "code_challenge_method": "S256"},
        follow_redirects=False)
    assert r.status_code == 302
    login_url = r.headers["location"]
    assert "/mcp/login" in login_url
    assert client.get(login_url).status_code == 200          # the form renders
    txn = parse_qs(urlparse(login_url).query)["txn"][0]
    r = client.post("/mcp/login", data={"txn": txn, "secret": login_secret},
                    follow_redirects=False)
    assert r.status_code == 302, r.text
    q = parse_qs(urlparse(r.headers["location"]).query)
    assert r.headers["location"].startswith(REDIRECT) and q["state"] == ["st4te"]
    return q["code"][0]


def _token(client, reg, grant: dict) -> dict:
    r = client.post("/token", data={
        "client_id": reg["client_id"], "client_secret": reg["client_secret"], **grant})
    assert r.status_code == 200, r.text
    return r.json()


def test_unauthenticated_mcp_is_401(auth_setup):
    client, _, _ = auth_setup
    r = client.post("/mcp", headers=MCP_HEADERS, json=INIT)
    assert r.status_code == 401 and "WWW-Authenticate" in r.headers


def test_full_connector_flow(auth_setup):
    client, provider, persist = auth_setup
    reg = _register(client)
    verifier, challenge = _pkce()
    code = _authorize(client, reg, challenge)

    tok = _token(client, reg, {"grant_type": "authorization_code", "code": code,
                               "redirect_uri": REDIRECT, "code_verifier": verifier})
    assert tok["token_type"].lower() == "bearer" and tok["refresh_token"]

    r = client.post("/mcp", headers={**MCP_HEADERS,
                                     "Authorization": f"Bearer {tok['access_token']}"},
                    json=INIT)
    assert r.status_code == 200 and "JobRadar" in r.text

    # refresh rotates: old refresh token dies, new pair works
    tok2 = _token(client, reg, {"grant_type": "refresh_token",
                                "refresh_token": tok["refresh_token"]})
    assert tok2["access_token"] != tok["access_token"]
    r = client.post("/token", data={
        "client_id": reg["client_id"], "client_secret": reg["client_secret"],
        "grant_type": "refresh_token", "refresh_token": tok["refresh_token"]})
    assert r.status_code == 400                              # rotated away

    # persistence: only sha256 hashes on disk; a fresh provider still accepts the token
    assert tok2["access_token"] not in persist.read_text()
    fresh = mcp_auth.SingleUserOAuthProvider("http://localhost", lambda: persist)
    assert anyio.run(fresh.load_access_token, tok2["access_token"]) is not None


def test_wrong_secret_and_bad_verifier_rejected(auth_setup):
    client, _, _ = auth_setup
    reg = _register(client)
    _, challenge = _pkce()

    with pytest.raises(AssertionError):                      # wrong login secret -> 401
        _authorize(client, reg, challenge, login_secret="nope")

    code = _authorize(client, reg, challenge)                # right secret, wrong verifier
    r = client.post("/token", data={
        "client_id": reg["client_id"], "client_secret": reg["client_secret"],
        "grant_type": "authorization_code", "code": code,
        "redirect_uri": REDIRECT, "code_verifier": "not-the-verifier" * 3})
    assert r.status_code == 400
    assert "code_verifier" in json.dumps(r.json())

    # a successful exchange consumes the code — replaying it must fail
    verifier2, challenge2 = _pkce()
    code2 = _authorize(client, reg, challenge2)
    _token(client, reg, {"grant_type": "authorization_code", "code": code2,
                         "redirect_uri": REDIRECT, "code_verifier": verifier2})
    r = client.post("/token", data={
        "client_id": reg["client_id"], "client_secret": reg["client_secret"],
        "grant_type": "authorization_code", "code": code2,
        "redirect_uri": REDIRECT, "code_verifier": verifier2})
    assert r.status_code == 400


def test_metadata_advertises_endpoints(auth_setup):
    client, _, _ = auth_setup
    meta = client.get("/.well-known/oauth-authorization-server").json()
    assert meta["issuer"].rstrip("/") == "http://localhost"
    for k in ("authorization_endpoint", "token_endpoint", "registration_endpoint"):
        assert k in meta
    assert "S256" in meta["code_challenge_methods_supported"]


def test_default_instance_stays_open_without_env():
    """No JSA_MCP_LOGIN_SECRET/ISSUER -> module default has no auth (tailnet mode)."""
    assert mcp_app.mcp._auth_server_provider is None
    with TestClient(mcp_app.create_mcp().streamable_http_app()) as client:
        assert client.post("/mcp", headers=MCP_HEADERS, json=INIT).status_code == 200
