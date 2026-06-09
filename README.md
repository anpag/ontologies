# Enterprise Ontology Repository

This repository acts as the single source of truth for the enterprise's semantic data models (ontologies). It is designed to cleanly separate foundational, domain, and application-specific semantics, and is the trigger point for automated downstream ingestion into the Knowledge Graph (e.g., BigQuery Property Graph).

## Repository Structure

The ontologies are organized hierarchically to promote reuse and interoperability:

*   **`src/core/`**: Foundational/Upper-level ontologies. These define the most abstract concepts (e.g., Time, Space, Process, Material Entity). *Example: Basic Formal Ontology (BFO).*
*   **`src/domain/`**: Domain-specific ontologies. These represent specific scientific or business domains. *Example: EMMO (Materials), OBI (Biomedical Investigations), QUDT (Units of Measure).*
*   **`src/application/`**: Application-specific ontologies. These are highly tailored to specific business use cases and inherit from the `core` and `domain` models. *Example: `henkel_demo.ttl` (Project -> Experiment -> Formulation).*
*   **`scripts/`**: Automation scripts for the CI/CD pipeline (e.g., Python `rdflib`/`owlrl` scripts for parsing OWL/TTL files into relational formats).
*   **`tests/`**: Unit tests and semantic validation rules to ensure ontology integrity before deployment.
*   **`docs/`**: Documentation on modeling guidelines, architectural decisions, and deployment processes.

## Workflow

1.  **Authoring:** Data Stewards modify `.owl` or `.ttl` files using standard tools (like Protégé).
2.  **Validation:** Commits trigger automated testing (`pytest` and semantic validations) to check for logical consistency and cyclic dependencies.
3.  **Deployment:** Merges to `main` trigger CI/CD pipelines that parse the ontologies, calculate deductive closures, and materialize the rules into the downstream database (e.g., BigQuery).
