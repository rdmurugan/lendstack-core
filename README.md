# idpflow-core

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![MCP server](https://img.shields.io/badge/MCP-server-7c3aed.svg)](https://modelcontextprotocol.io)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Stars](https://img.shields.io/github/stars/rdmurugan/idpflow-core?style=social)](https://github.com/rdmurugan/idpflow-core)

> **Intelligent Document Processing (IDP) as an MCP server, powered by [LandingAI ADE](https://va.landing.ai).**

Ingest documents from anywhere, classify them, **stack them in your reviewer's exact order**,
extract every field with **page-level provenance and confidence**, and render a review-ready
package (PDF + JSON). Built for **regulated finance and healthcare**, where every value has to
trace back to its source. Bring your own LandingAI key.

**Works with:** Claude · Lyzr AI · LangGraph · CrewAI · Databricks · any MCP client

```
documents (any source)  ─▶  classify  ─▶  extract (ADE, grounded)  ─▶  stack  ─▶  review package
  upload / SFTP / S3 /                       value + page + bbox                    PDF + JSON,
  email / LOS export                         + confidence                          ungrounded flagged
```

## Why it exists

Most document AI hands you a wall of text and leaves you to figure out the rest. idpflow-core
keeps every value **grounded** so the output holds up where the stakes are real:

- **ADE done right (two steps).** `parse` turns a document into layout-aware markdown with visual
  grounding, then `extract` maps a JSON schema to typed fields with source references. Every field
  points back to the page and box it came from.
- **Groundedness is the audit signal.** A value that maps to a source chunk is examinable. An
  ungrounded value is flagged for a human, automatically.
- **Source-agnostic.** Works on any list of files, however they arrived.
- **Configurable stacking.** Assemble a document set into the exact order a reviewer expects.
- **Human-in-the-loop.** It surfaces grounded data for a person to act on. It makes no decisions.

## Use cases

| Domain | What it does |
|---|---|
| **Lending / banking** | Stack a loan or credit file (1003, paystubs, W-2, bank statements, ID), extract income/identity/collateral fields with provenance, hand a reviewer a decision-ready package |
| **Healthcare ops** | Order an intake or prior-auth or claims packet, extract the fields a reviewer needs, flag anything ungrounded |
| **Any regulated back office** | Turn a folder of PDFs into stacked, grounded, audit-ready data |

## Tools (MCP)

| Tool | Purpose |
|---|---|
| `extract_document` | ADE-extract one doc into fields + confidence + page/bbox provenance |
| `classify_document` | Detect a document's type (hint, then ADE markdown, then filename) |
| `stack_documents` | Order a document set into a configured stack (or a `custom_order`) |
| `process_documents` | Ingest, classify, extract, stack into a `DocumentPackage` |
| `render_document_package` | Render a combined PDF (cover + source docs in order) + JSON sidecar |

## Quickstart (60 seconds, no API key)

```bash
git clone https://github.com/rdmurugan/idpflow-core.git && cd idpflow-core
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e .

python examples/make_sample_docs.py     # synthetic loan package
python examples/direct_library.py        # runs the whole pipeline in STUB mode (free)
```

Without `VISION_AGENT_API_KEY`, every tool returns synthetic data so you can try the full
pipeline before spending a cent on ADE. Add the key (`cp .env.example .env`) for live extraction.

Run it as an MCP server: `idpflow-core` (stdio) or inspect it with
`npx @modelcontextprotocol/inspector idpflow-core`.

## Use it with your stack

Copy-paste setup for **Claude, Lyzr AI, LangGraph, CrewAI, and Databricks** is in
[`docs/INTEGRATIONS.md`](docs/INTEGRATIONS.md), and runnable scripts are in
[`examples/`](examples/).

## Governance and regulated industries

The reason this is built the way it is:

- **Provenance on every value** (page + box + confidence) gives you an examinable audit trail.
- **No autonomous decisions.** Ungrounded or low-confidence values are flagged for human review.
- **OAuth 2.1** on the remote server. It refuses to start unauthenticated.
- **Deploy in your own environment** (your cloud, your Databricks workspace) so PII never leaves
  your boundary. See [`docs/DEPLOY.md`](docs/DEPLOY.md).

## Databricks (batch / lakehouse)

Run the same pipeline as a Databricks job: documents in a Unity Catalog Volume to **Delta
tables**. See [`databricks/`](databricks/).

## Security: enable the secret-guard hook (once per clone)

```bash
git config core.hooksPath .githooks   # blocks commits that stage .env or key/secret values
```

## Contributing

PRs, use cases, and connectors are welcome, especially from lending, banking, and healthcare ops.
See [CONTRIBUTING.md](CONTRIBUTING.md). Good first contributions: new stack profiles in
`stacking.py`, new extraction schemas in `schemas.py`, or a connector for your document source.

## License

Apache-2.0. ADE is a LandingAI product. You supply your own key; this project does not bundle or
resell it.
