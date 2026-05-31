"""OAuth 2.1 for the remote MCP server.

The MCP server is an OAuth **Resource Server**: it verifies bearer tokens issued by an
external Authorization Server / IdP (Auth0, Okta, Entra ID, etc.) and never handles
credentials itself. This is the model Claude Marketplace + the Connectors Directory expect.

Two modes, selected by environment:
  - Production: validate a JWT against the IdP's JWKS (issuer + audience + scopes).
  - Dev: a single static bearer token (MCP_DEV_BEARER_TOKEN) — never use in production.

If neither is configured, build_auth() returns (None, None) → the server runs unauthenticated
(fine for local stdio dev, NEVER for a public remote endpoint).
"""

from __future__ import annotations

import os
import time

import anyio
import jwt
from jwt import PyJWKClient
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings


class JWTVerifier(TokenVerifier):
    """Validates RS256 JWTs from an IdP via its JWKS endpoint."""

    def __init__(self, issuer: str, audience: str, jwks_url: str, required_scopes: list[str]):
        self.issuer = issuer
        self.audience = audience
        self.required_scopes = required_scopes
        self._jwks = PyJWKClient(jwks_url)

    def _decode(self, token: str) -> dict:
        signing_key = self._jwks.get_signing_key_from_jwt(token).key
        return jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=self.audience,
            issuer=self.issuer,
            options={"require": ["exp", "iat"]},
        )

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            claims = await anyio.to_thread.run_sync(self._decode, token)
        except Exception:  # noqa: BLE001 - any validation failure => deny
            return None

        scope_str = claims.get("scope") or claims.get("scp") or ""
        scopes = scope_str.split() if isinstance(scope_str, str) else list(scope_str)
        if self.required_scopes and not set(self.required_scopes).issubset(scopes):
            return None

        return AccessToken(
            token=token,
            client_id=claims.get("azp") or claims.get("client_id") or claims.get("sub", ""),
            scopes=scopes,
            expires_at=claims.get("exp"),
            subject=claims.get("sub"),
            claims=claims,
        )


class StaticTokenVerifier(TokenVerifier):
    """Dev-only: accepts a single shared bearer token. Not for production."""

    def __init__(self, token: str, scopes: list[str]):
        self._token = token
        self._scopes = scopes

    async def verify_token(self, token: str) -> AccessToken | None:
        if token != self._token:
            return None
        return AccessToken(
            token=token,
            client_id="dev-static",
            scopes=self._scopes,
            expires_at=int(time.time()) + 3600,
            subject="dev",
        )


def build_auth() -> tuple[TokenVerifier | None, AuthSettings | None]:
    """Construct (token_verifier, AuthSettings) from env, or (None, None) if unconfigured."""
    issuer = os.getenv("OAUTH_ISSUER")
    audience = os.getenv("OAUTH_AUDIENCE")
    resource = os.getenv("MCP_RESOURCE_URL")
    scopes = [s.strip() for s in os.getenv("OAUTH_REQUIRED_SCOPES", "").split(",") if s.strip()]
    dev_token = os.getenv("MCP_DEV_BEARER_TOKEN")

    if issuer and audience and resource:
        jwks_url = os.getenv("OAUTH_JWKS_URL") or issuer.rstrip("/") + "/.well-known/jwks.json"
        verifier = JWTVerifier(issuer, audience, jwks_url, scopes)
        settings = AuthSettings(
            issuer_url=issuer,
            resource_server_url=resource,
            required_scopes=scopes or None,
        )
        return verifier, settings

    if dev_token and resource:
        verifier = StaticTokenVerifier(dev_token, scopes)
        settings = AuthSettings(
            issuer_url=resource,
            resource_server_url=resource,
            required_scopes=scopes or None,
        )
        return verifier, settings

    return None, None
