# Deploying idpflow-core as a remote MCP server

The remote (streamable-HTTP) transport is what hosted orchestrators (Claude Connectors, Lyzr,
etc.) connect to. It **requires OAuth 2.1** — the server refuses to start in remote mode without
it (override only with `MCP_ALLOW_INSECURE=1` behind your own trusted gateway).

## Auth model (OAuth 2.1 Resource Server)

This server is a **resource server**: it validates bearer tokens issued by an external
Authorization Server (your IdP — Auth0, Okta, Entra ID, Cognito…). It never handles user
credentials. The client obtains a token from the IdP and presents it; the server verifies the
JWT against the IdP's JWKS, checks issuer/audience/expiry/scopes, and serves the OAuth Protected
Resource Metadata the MCP spec expects.

```
client ──token request──▶  IdP  ──issues JWT──▶ client
client ──MCP call + Bearer JWT──▶  idpflow-core (verifies JWT vs IdP JWKS) ──▶ tools
```

### Required env (production)
| Var | Example | Notes |
|---|---|---|
| `OAUTH_ISSUER` | `https://your-tenant.us.auth0.com/` | IdP issuer |
| `OAUTH_AUDIENCE` | `idpflow-api` | this server's API identifier |
| `MCP_RESOURCE_URL` | `https://example.com/mcp` | this server's public URL |
| `OAUTH_JWKS_URL` | (auto) | defaults to `<issuer>/.well-known/jwks.json` |
| `OAUTH_REQUIRED_SCOPES` | `idpflow.read` | optional, CSV |

### Dev (single static token — never production)
```
MCP_DEV_BEARER_TOKEN=<random-dev-token>
MCP_RESOURCE_URL=http://localhost:8080/mcp
```

## Run with Docker

```bash
docker build -t idpflow-core .

docker run --rm -p 8080:8080 \
  -e OAUTH_ISSUER=https://your-tenant.us.auth0.com/ \
  -e OAUTH_AUDIENCE=idpflow-api \
  -e MCP_RESOURCE_URL=https://example.com/mcp \
  -e VISION_AGENT_API_KEY=...   # your LandingAI key for live extraction \
  idpflow-core
```

The image runs as a non-root user, defaults to `MCP_TRANSPORT=streamable-http` on port 8080,
and **exits immediately** if OAuth env is absent (unless `MCP_ALLOW_INSECURE=1`).

## Data residency

Deploy this **inside the customer's environment** (their cloud / container service) so documents
and extracted data never leave their boundary — the deployment boundary is the trust boundary.
The customer points their own IdP + LandingAI key at the container.
