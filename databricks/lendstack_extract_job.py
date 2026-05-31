# Databricks notebook source
# MAGIC %md
# MAGIC # lendstack-core on Databricks
# MAGIC
# MAGIC Batch document extraction + stacking on the lakehouse. Reads documents from a Unity
# MAGIC Catalog **Volume**, runs the same `lendstack-core` pipeline (classify -> ADE extract ->
# MAGIC stack), and writes **grounded** results to governed **Delta tables**:
# MAGIC
# MAGIC - `<catalog>.<schema>.lendstack_extracted_fields` — one row per extracted field, with
# MAGIC   confidence + source page + grounded flag
# MAGIC - `<catalog>.<schema>.lendstack_document_stacks` — one row per stacked document
# MAGIC
# MAGIC **Bring your own LandingAI key** (stored as a Databricks secret). Documents are grouped
# MAGIC into "packages" by their immediate sub-folder under the volume path.

# COMMAND ----------
# MAGIC %pip install git+https://github.com/rdmurugan/lendstack-core.git

# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
# MAGIC %md ## Config

# COMMAND ----------
dbutils.widgets.text("catalog", "main", "Unity Catalog")
dbutils.widgets.text("schema", "lending", "Schema")
dbutils.widgets.text("volume_path", "/Volumes/main/lending/loan_docs", "Volume path with documents")
dbutils.widgets.text("profile", "mortgage", "Stack profile (mortgage|auto_indirect|auto_direct)")
dbutils.widgets.text("secret_scope", "lendstack", "Databricks secret scope")
dbutils.widgets.text("secret_key", "vision_agent_api_key", "Secret key for the LandingAI key")

CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")
VOLUME_PATH = dbutils.widgets.get("volume_path")
PROFILE = dbutils.widgets.get("profile")
SECRET_SCOPE = dbutils.widgets.get("secret_scope")
SECRET_KEY = dbutils.widgets.get("secret_key")

import os

# ADE key from Databricks secrets (never hard-code). Omit to run lendstack-core in STUB mode.
try:
    os.environ["VISION_AGENT_API_KEY"] = dbutils.secrets.get(scope=SECRET_SCOPE, key=SECRET_KEY)
    print("LandingAI key loaded from secret scope.")
except Exception as e:  # noqa: BLE001
    print(f"No secret found ({e}); running in STUB mode (synthetic data, no API cost).")

spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")

# COMMAND ----------
# MAGIC %md ## Discover document packages
# MAGIC Each immediate sub-folder under the volume path is treated as one loan package.

# COMMAND ----------
from pathlib import Path

def discover_packages(root: str) -> dict[str, list[str]]:
    """Return {package_id: [file_paths]} grouping files by their immediate sub-folder."""
    packages: dict[str, list[str]] = {}
    root_p = Path(root)
    for dirpath, _dirnames, filenames in os.walk(root):
        docs = [
            str(Path(dirpath) / f)
            for f in filenames
            if f.lower().endswith((".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"))
        ]
        if not docs:
            continue
        rel = Path(dirpath).relative_to(root_p)
        package_id = rel.parts[0] if rel.parts else root_p.name
        packages.setdefault(package_id, []).extend(docs)
    return packages

packages = discover_packages(VOLUME_PATH)
print(f"Discovered {len(packages)} package(s):")
for pid, docs in list(packages.items())[:10]:
    print(f"  {pid}: {len(docs)} document(s)")

# COMMAND ----------
# MAGIC %md ## Run the pipeline and assemble rows

# COMMAND ----------
from lendstack_core.ade_client import ADEClient
from lendstack_core.package import build_package
from lendstack_core.models import DocInput

ade = ADEClient()  # reads VISION_AGENT_API_KEY from env; stub if absent

field_rows = []
stack_rows = []
for package_id, docs in packages.items():
    pkg = build_package(
        package_id,
        [DocInput(file_path=p) for p in docs],
        profile=PROFILE,
        client=ade,
    )
    for k in pkg.key_fields:
        field_rows.append(
            {
                "package_id": pkg.package_id,
                "profile": pkg.profile,
                "source_doc": k.source_doc.value,
                "field_name": k.name,
                "value": k.value,
                "confidence": k.confidence,
                "grounded": k.grounded,
                "page": k.page,
                "needs_review": k.needs_review,
            }
        )
    for it in pkg.ordered_stack:
        stack_rows.append(
            {
                "package_id": pkg.package_id,
                "position": it.position,
                "doc_type": it.doc_type.value,
                "file_path": it.file_path,
                "in_profile": it.in_profile,
                "overall_confidence": it.overall_confidence,
                "review_required": it.review_required,
            }
        )

print(f"{len(field_rows)} field rows, {len(stack_rows)} stack rows")

# COMMAND ----------
# MAGIC %md ## Write to governed Delta tables

# COMMAND ----------
fields_tbl = f"{CATALOG}.{SCHEMA}.lendstack_extracted_fields"
stacks_tbl = f"{CATALOG}.{SCHEMA}.lendstack_document_stacks"

if field_rows:
    spark.createDataFrame(field_rows).write.mode("overwrite").option(
        "overwriteSchema", "true"
    ).saveAsTable(fields_tbl)
if stack_rows:
    spark.createDataFrame(stack_rows).write.mode("overwrite").option(
        "overwriteSchema", "true"
    ).saveAsTable(stacks_tbl)

print(f"Wrote {fields_tbl} and {stacks_tbl}")
display(spark.table(fields_tbl))

# COMMAND ----------
# MAGIC %md
# MAGIC ## Optional: scale extraction across the cluster
# MAGIC For large document volumes, parallelize per-document extraction with a `pandas_udf`.
# MAGIC ADE is a network API — mind its rate limits and keep cluster concurrency reasonable.

# COMMAND ----------
import pandas as pd
from pyspark.sql.functions import pandas_udf
from pyspark.sql.types import StringType

@pandas_udf(StringType())
def extract_doc_json(file_paths: pd.Series, doc_types: pd.Series) -> pd.Series:
    import json
    from lendstack_core.ade_client import ADEClient
    from lendstack_core.models import DocType
    client = ADEClient()  # one client per task
    out = []
    for fp, dt in zip(file_paths, doc_types):
        try:
            res = client.extract(fp, DocType(dt) if dt else DocType.OTHER)
            out.append(json.dumps([f.model_dump() for f in res.fields], default=str))
        except Exception as e:  # noqa: BLE001
            out.append(json.dumps({"error": str(e)}))
    return pd.Series(out)

# Example:
# docs_df = spark.createDataFrame([(p, "paystub") for p in some_paths], ["file_path", "doc_type"])
# docs_df.withColumn("fields_json", extract_doc_json("file_path", "doc_type")).display()
