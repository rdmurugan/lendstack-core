# idpflow-core

**An MCP server for agentic document extraction + stacking, powered by [LandingAI ADE](https://va.landing.ai).**

Ingest documents from any source → classify → **stack them in a configurable order** → extract
typed fields with **page-level provenance and confidence** → render a combined review package
(PDF + JSON). Callable by Claude, or any MCP-speaking orchestrator. **Bring your own LandingAI key.**

## Why

Most document-AI wrappers hand you a blob of text. idpflow-core keeps every value **grounded**:

- **ADE two-step done right** — `parse` (document → layout-aware markdown + grounded chunks with
  page/bbox) then `extract` (markdown + JSON schema → typed fields + source references). Each
  field maps back to where it came from.
- **Groundedness as the audit signal** — ADE returns *references*, not a blind confidence number.
  A value that maps to a source chunk is examinable; an ungrounded value is auto-flagged for review.
- **Document-source-agnostic** — works on any list of files (upload portal, SFTP/S3, email, export).
- **Configurable stacking** — assemble a document set into the exact order a reviewer wants.
- **Human-in-the-loop** — surfaces grounded data for a person to act on; makes no decisions.

## Tools

| Tool | Purpose |
|---|---|
| `extract_document` | ADE-extract one doc → fields + confidence + page/bbox provenance |
| `classify_document` | Detect a doc's type (hint → ADE markdown → filename) |
| `stack_documents` | Order a document set into a configured stack (or `custom_order`) |
| `process_documents` | Ingest → classify → extract → stack → `DocumentPackage` |
| `render_document_package` | Render a combined PDF (cover + source docs in stack order) + JSON sidecar |

## Quickstart

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env        # add VISION_AGENT_API_KEY for live extraction
                            # (omit it to run in STUB mode — synthetic data, no API cost)

idpflow-core              # stdio (Claude Desktop / local dev)
npx @modelcontextprotocol/inspector idpflow-core
```

Without `VISION_AGENT_API_KEY`, every tool works end-to-end with synthetic data so you can wire
up orchestration before spending a cent on ADE.

## Remote mode (OAuth 2.1)

```bash
OAUTH_ISSUER=https://your-tenant.us.auth0.com/ OAUTH_AUDIENCE=your-api \
MCP_RESOURCE_URL=https://example.com/mcp \
MCP_TRANSPORT=streamable-http idpflow-core
```

The server acts as an OAuth **resource server**, validating IdP-issued JWTs (static-token dev
mode also supported). It **refuses to start** in remote mode without auth. Container:
`docker build -t idpflow-core .`

## Security: enable the secret-guard hook (once per clone)

```bash
git config core.hooksPath .githooks   # blocks commits that stage .env or key/secret values
```

## Databricks (batch / lakehouse)

Run the same pipeline as a Databricks job: documents in a Unity Catalog Volume → classify /
extract / stack → grounded results in **Delta tables**. See [`databricks/`](databricks/) for the
notebook (`idpflow_extract_job.py`) and setup. Runs **inside the customer's workspace**, so
documents and extracted PII never leave their boundary.

## Use it with your stack

Step-by-step setup for **Claude, Databricks, Lyzr AI, LangGraph, and CrewAI** →
[`docs/INTEGRATIONS.md`](docs/INTEGRATIONS.md).

## Stack profiles

Default profiles (`mortgage`, `auto_indirect`, `auto_direct`) live in `stacking.py` and are
examples — add your own, or pass `custom_order`. Extraction schemas per document type live in
`schemas.py`.

## License

Apache-2.0. ADE itself is a LandingAI product — you supply your own key; this project does not
bundle or resell it.
