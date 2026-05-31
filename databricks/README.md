# idpflow-core on Databricks

Run the document extraction + stacking pipeline as a **lakehouse batch job**: documents in a
Unity Catalog Volume → classify / extract / stack → grounded results in Delta tables. Same
`idpflow-core` library as the MCP server; this is the batch/at-scale runtime.

## What it produces

| Table | Grain |
|---|---|
| `<catalog>.<schema>.idpflow_extracted_fields` | one row per extracted field (value, confidence, page, grounded, needs_review) |
| `<catalog>.<schema>.idpflow_document_stacks` | one row per stacked document (position, doc_type, review_required) |

## Setup

1. **Store your LandingAI key as a Databricks secret** (never hard-code it):
   ```bash
   databricks secrets create-scope idpflow
   databricks secrets put-secret idpflow vision_agent_api_key
   ```
   Omit this to run in **stub mode** (synthetic data, no API cost) to validate the flow first.

2. **Put documents in a Unity Catalog Volume**, grouped one sub-folder per loan package:
   ```
   /Volumes/main/lending/loan_docs/
     LN-2026-0001/  (1003.pdf, paystub.pdf, w2.pdf, ...)
     LN-2026-0002/  (...)
   ```

3. **Import `idpflow_extract_job.py`** as a notebook (it's in Databricks source format) and
   set the widgets: `catalog`, `schema`, `volume_path`, `profile`, `secret_scope`, `secret_key`.

4. **Run.** It `%pip install`s `idpflow-core` from GitHub, processes each package, and writes
   the two Delta tables. Schedule it as a Databricks Job for recurring batches.

## Scale

The last cell shows a `pandas_udf` that parallelizes per-document extraction across the cluster.
ADE is a network API — mind its rate limits and keep cluster concurrency reasonable.

## Data residency

Because this runs **inside the customer's Databricks workspace**, loan documents and extracted
PII never leave their boundary — the lakehouse is the trust boundary. This is the same
deploy-in-the-customer's-environment posture as the remote MCP server.

## Notes

- Requires Databricks Runtime with Unity Catalog. The volume path is a FUSE mount, so plain
  Python file I/O works.
- Until `idpflow-core` is published to PyPI, the notebook installs it from the Git repo.
