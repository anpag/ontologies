# Enterprise Ontology Repository

This repository acts as the single source of truth for the enterprise's semantic data models (ontologies). It is designed to cleanly separate foundational, domain, and application-specific semantics, and serves as the trigger point for automated downstream ingestion into the Knowledge Graph (e.g., BigQuery Property Graph).

## Architecture & CI/CD Pipeline

To ensure the ontology is governed, version-controlled, and seamlessly synced with the analytical database, we have implemented an automated, event-driven CI/CD architecture running on Google Cloud:

1. **Authoring (GitHub):** Data Stewards define and update the semantic rules (e.g., `src/application/henkel_demo.ttl`) and push changes via pull requests to GitHub.
2. **Tag Release (GitHub Actions):** When a semantic version tag (e.g., `v1.0.0`) is pushed, a GitHub Action workflow is triggered.
3. **Authentication (Workload Identity Federation):** The GitHub Action securely authenticates to Google Cloud using Workload Identity Federation, eliminating the need to store long-lived service account keys as secrets.
4. **Event Trigger (Pub/Sub & Eventarc):** The action publishes a JSON payload containing the Git commit hash and tag version to a Pub/Sub topic (`github-webhook-topic`). Eventarc routes this message directly to our Cloud Run ingestion service.
5. **Ontology Materialization (Cloud Run):** 
   - A containerized Python Flask service (`scripts/app.py`) receives the payload and extracts the version metadata.
   - It dynamically downloads the `.ttl` ontology file corresponding to that specific git tag.
   - It pre-parses the file using `rdflib` to normalize the syntax into RDF/XML.
   - It invokes the `owlready2` HermiT deductive reasoning engine to compute the logical closure (inferring all inherited relationships).
   - It extracts the expanded ontology into three structured components: **Classes**, **Topology Rules** (Object Properties), and **Data Properties**.
6. **Data Staging (BigQuery):** Finally, the service loads the data natively into the BigQuery staging dataset (`kg_ontology_staging`). Crucially, it uses the BigQuery API to automatically update the table descriptions with the semantic tag/commit hash, providing end-to-end data lineage directly in the database.
7. **Human-In-The-Loop Validation & Promotion (Dataform):** A Data Engineer or Data Steward manually reviews the staged data and triggers the Dataform pipeline. Dataform runs a suite of SQL assertions (e.g., verifying referential integrity of all relationships). If the assertions pass, Dataform safely promotes the validated rules into the `kg_ontology_production` dataset and constructs the final BigQuery Property Graph. This explicit manual trigger ensures a human always signs off on production-breaking semantic changes.

## Repository Structure

The ontologies and supporting services are organized as follows:

*   **`src/core/`**: Foundational/Upper-level ontologies defining abstract concepts.
*   **`src/domain/`**: Domain-specific ontologies (e.g., specific scientific domains).
*   **`src/application/`**: Application-specific ontologies tailored to specific business use cases (e.g., `henkel_demo.ttl`).
*   **`scripts/`**: Contains the source code (`app.py`, `main.py`) and `Dockerfile` for the Cloud Run materialization service.
*   **`cloudbuild.yaml`**: The CI/CD configuration to build and deploy the Cloud Run ingestion container automatically on updates to the `scripts/` directory.
*   **`.github/workflows/`**: Contains `trigger_ingestion.yml` which defines the GitHub Actions pipeline.

## How to Trigger the Pipeline

1. Make changes to the ontology files (e.g., `.ttl` files in `src/`).
2. Commit and push the changes to `main`.
3. Tag the repository with a semantic version:
   ```bash
   git tag v1.0.2
   git push origin v1.0.2
   ```
4. This will trigger the pipeline. The updated ontology will be reasoned and materialized in BigQuery within a few minutes, carrying the new version tag in the table descriptions.

## Further Documentation

* **[Semantic "Clean Room" Architecture](docs/SEMANTIC_CLEAN_ROOM_ARCHITECTURE.md)**: Explains the decoupling of raw extraction from canonicalization using SKOS and QUDT, and the human-in-the-loop DLQ feedback process.
