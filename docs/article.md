# Document AI You Can Audit: An Open-Source IDP Layer on LandingAI ADE

*Why regulated teams need grounded extraction, and how an experiment became something I would actually put in front of a credit union or a hospital.*

## The quiet problem nobody wants to own

If you have ever worked a loan file or a claims queue, you know the shape of this problem. A package arrives as a pile of PDFs. Pay stubs, W-2s, bank statements, a 1003, an ID. Or in healthcare: an intake form, a prior authorization, clinical notes, a stack of supporting documents. Someone has to open each one, figure out what it is, put them in the right order, read the values that matter, type them somewhere, and sign off.

It is slow, it is repetitive, and in a regulated business it is risky. A wrong field is not a typo you fix later. It can be an adverse action sent on bad grounds, a compliance finding, a denial that should have been an approval. The cost of being wrong is asymmetric, which is exactly why these teams have been cautious about automating it.

For years the tooling did not help. Traditional OCR gives you a wall of text and leaves the hard part, knowing what each value means and where it came from, to a human. The newer LLM approaches are fluent but confident in a way that is dangerous here. A model that says "the borrower's income is 6,500" without telling you where it read that is not something you can put in front of an examiner.

## What changed for me: LandingAI ADE

I spent time with LandingAI's Agentic Document Extraction, and it moved this problem from "interesting demo" to "I would build on this."

ADE works in two steps, and the split is the whole point.

First it **parses** a document into layout-aware markdown with visual grounding. It sees the page the way a person does, including tables, form fields, and structure, and it keeps track of where everything sits on the page.

Then it **extracts** structured fields against a JSON schema you provide. You ask for the fields you care about, and it returns typed values.

The part I care about is what comes back with those values. A grounded field is tied to its source: the page, the bounding box, and a reference to the chunk it came from. In a regulated workflow, "the model said so" does not hold up. "This value came from page 3, box 4, here are the coordinates" does. That traceability is the difference between a tool you can demo and a tool you can deploy.

There is a subtle but important detail here. ADE's extract step returns references, not a single blind confidence number. So the honest audit signal is groundedness. If a value maps to a real piece of the source document, you can check it. If it does not, that is a red flag, and you want it surfaced rather than buried. That property turned out to be the foundation for everything I built on top.

## The build: idpflow-core

So I wrote a thin open-source layer on top of ADE and released it as **idpflow-core**. IDP stands for Intelligent Document Processing, which is exactly what this is, and the name is domain-neutral on purpose. The same machinery serves lending and healthcare.

It is an MCP server, which means any MCP-speaking orchestrator can drive it. It does the unglamorous work that document-heavy teams actually need:

1. **Ingest** documents from anywhere. An upload portal, a watched SFTP or S3 folder, an email intake, an export from a system of record. The core does not care how they arrived.
2. **Classify** each document so the right schema and the right stack position get applied.
3. **Stack** the documents into the exact order a reviewer expects. This is configurable, because a mortgage credit file, an auto loan stip set, and a healthcare intake all have their own conventions.
4. **Extract** every document through ADE, carrying grounding and provenance, with confidence on grounded values.
5. **Render** a review-ready package: a combined PDF with a cover sheet that ties each value to its source page, plus a JSON sidecar for systems that want structured data.

And then it stops. It surfaces grounded data for a person to act on. It does not approve, deny, score, or rank anyone. That boundary is deliberate.

## Why governance is built in, not bolted on

The reason this works for regulated industries is that the properties an auditor cares about are structural, not promised on a slide.

**Provenance on grounded values.** Page, box, and confidence travel with the data. Values that cannot be grounded are flagged for review rather than trusted, so you get an examinable trail by default.

**No autonomous decisions.** The tools output data and a review queue. They never approve, deny, score, or rank. A person decides.

**Authentication that fails closed.** The remote server uses OAuth 2.1 and refuses to start without it. There is no accidental open endpoint.

**Run it in your own environment.** You can host it inside your own cloud or your Databricks workspace, so the orchestration, stacking, storage, and extracted data stay within your boundary. One honest caveat: extraction itself calls LandingAI's ADE API, so documents are sent to ADE for parsing. Stub mode is fully local, and LandingAI offers on-prem and VPC options where that step also has to stay inside. If you handle regulated data, treat ADE as a sub-processor in your data agreements, the same way you would any cloud service.

None of this is exotic. It is the posture a bank examiner, an auditor, or a privacy review expects, expressed in the architecture instead of in marketing copy.

## Portable on purpose

One thing I wanted from the start was to avoid locking the work to a single platform. So idpflow-core is one core that many tools can call.

It runs as an MCP server for **Claude**, and registers in **Lyzr AI** Agent Studio. It plugs into **LangGraph** through the standard MCP adapters and into **CrewAI** through its MCP tool adapter. And for batch work at scale, it runs as a **Databricks** job that reads documents from a Unity Catalog Volume and writes grounded results into Delta tables.

Build once, orchestrate anywhere. To be precise about maturity: this is an early project. The core pipeline is validated against live ADE, and the framework integrations are example-level today. Because it speaks MCP, it works with any MCP-conformant client.

## From experiment to implementation

This started as a question. Could agentic document extraction plus the Model Context Protocol actually handle the messy reality of regulated document work, end to end, without giving up the audit trail.

The honest answer turned out to be yes, and the path from experiment to something of production-level quality was shorter than I expected, largely because ADE's grounding gave me a foundation I did not have to invent. I validated the full pipeline on real documents, wrapped it in the governance posture regulated teams need, containerized it, and documented it for five different runtimes.

It is Apache-2.0 and open. It runs in stub mode with no API key, so you can try the whole pipeline in about a minute, for free, before deciding whether it fits.

## Try it, and tell me what you are drowning in

The repository is here: **github.com/rdmurugan/idpflow-core**

If you work in lending, banking, or healthcare operations, I would genuinely value your input. The most useful contributions are new stacking profiles for document sets you handle, new extraction schemas, and connectors for the sources your documents arrive from. PRs and issues are welcome.

And real credit to the LandingAI team for ADE. The grounding is the unlock. Everything I built sits on top of that one good idea, that a machine-read value should always be able to point back to where it came from.
