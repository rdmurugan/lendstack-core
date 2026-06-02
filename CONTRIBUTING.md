# Contributing to idpflow-core

Thanks for your interest. This project turns LandingAI ADE into a grounded, MCP-first document
processing layer for regulated workflows, and it gets better with real-world use cases.

## Ways to help

- **New stack profiles.** Add an ordering for a document set you work with (a loan program, a
  healthcare packet, a KYC file) in `src/idpflow_core/stacking.py`.
- **New extraction schemas.** Add per-document-type field schemas in `src/idpflow_core/schemas.py`.
- **Connectors.** Adapters that feed documents in from a source you use (a portal, a queue, an LOS).
- **Docs and examples.** Improve the integration guides or add an example for another orchestrator.
- **Bug reports.** Open an issue with a minimal repro. Stub mode (no API key) is great for this.

## Dev setup

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
git config core.hooksPath .githooks    # secret-guard hook (blocks staged keys/.env)

python examples/make_sample_docs.py
python examples/direct_library.py      # runs in stub mode, no key needed
```

## Before you open a PR

- Keep the **human-in-the-loop** posture: this layer surfaces grounded data, it does not make
  decisions. Please don't add tools that auto-approve, auto-deny, or score/rank applicants.
- Keep values **grounded**. New extraction paths should carry provenance and flag ungrounded data.
- Run the examples in stub mode to confirm nothing broke.
- Do not commit secrets. The secret-guard hook will block `.env` and key-looking values.

## Conduct

Be respectful and constructive. We are here to build something useful together.
