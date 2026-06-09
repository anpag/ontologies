# Ontology Ingestion Pipeline

## Overview

The `ontology_ingestion` module is responsible for parsing, reasoning, and materializing domain ontologies into a structured format within BigQuery. This process establishes the foundational governance layer for the entire Semantic Graph Pipeline, ensuring that all subsequent data extractions and graph constructions adhere to a strictly defined knowledge model.

### Why Ontology-Driven Schema Definition Makes Sense
Having the ontology act as the strict schema definition for the resulting graph in BigQuery is a deliberate architectural pattern designed for rigorous data governance:
*   **Domain Experts Own the Data Model:** Data engineers do not define the schema based on business requirements. The domain experts author the ontology, and the pipeline enforces it.
*   **Single Source of Truth for Governance:** Using the same ontology for the knowledge graph, extraction pipelines, and the data warehouse guarantees semantic consistency. An entity (like "Patient") means the exact same thing across all systems.
*   **Automated Validation:** Instead of writing custom SQL data quality checks, the pipeline programmatically uses the ontology's `domain` and `range` rules to automatically enforce valid relationships.
## Who is Responsible for Defining the Graph Hierarchy and Structure?

The **Ontology** serves as the single source of truth for the graph's hierarchy and structure. 

The engineering pipelines do not arbitrarily decide how nodes relate to one another or what properties a node should possess. Instead, the graph structure is dictated entirely by the domain experts and knowledge engineers who author the ontology. 

Specifically:
*   **Permissible Nodes:** Defined by the Ontology Classes.
*   **Graph Topology (Edges):** Defined by the Object Properties (and their respective domains and ranges).
*   **Node Schemas (Attributes):** Defined by the Data Properties.

By centralizing these definitions in the ontology, the system guarantees that the resulting Property Graph is semantically sound and aligned with the domain's formal knowledge representation.

## Core Concepts

To understand the ingestion process, it is important to be familiar with the underlying Semantic Web standards used to represent the knowledge graph schema:

*   **Ontology:** A formal, explicit specification of a shared conceptualization. It defines the entities, properties, and relationships that exist within a specific domain.
*   **OWL (Web Ontology Language):** A computational logic-based language designed to represent rich and complex knowledge about things, groups of things, and relations between things. It provides the expressiveness needed to model complex constraints.
*   **RDFS (Resource Description Framework Schema):** Provides the basic vocabulary to describe properties and classes. Key constructs include `rdfs:subClassOf` (defining hierarchy), `rdfs:domain` (what type of node a property belongs to), and `rdfs:range` (what type of node or value a property points to).
*   **SKOS (Simple Knowledge Organization System):** A W3C recommendation designed for representation of thesauri, classification schemes, and taxonomies. In this pipeline, it is heavily used to capture rich metadata such as definitions (`skos:definition`), synonyms/alternative labels (`skos:altLabel`), and examples (`skos:example`).

## The Role of the Reasoning Engine

A critical part of the ingestion process is the use of a reasoning engine (specifically, HermiT via Owlready2) before data is persisted to BigQuery.

### Why is Materialization Important?

Ontologies are highly hierarchical and often rely on implicit knowledge. For example, if the ontology states that a `ClinicalTrial` is a subclass of `Study`, and that a `Study` has a property called `hasSponsor`, it is implicitly true that a `ClinicalTrial` can also have a `hasSponsor` property.

Relational databases and data warehouses like BigQuery are not designed to natively traverse these complex inference chains on the fly during data validation. 

The reasoning engine parses the OWL file and **materializes** this implicit knowledge into explicit, flat structures. It computes the inferred class hierarchies, expands domain/range restrictions, and resolves logical constraints. 

By running the reasoner during the ingestion phase, we extract an explicit, flattened set of rules:
1.  **Rich Class Dictionary (`onto_classes`):** A flat table of all permissible node types and their metadata.
2.  **Topology Rules (`onto_rules`):** Explicit source-to-target relationship rules defining exactly which nodes can connect to which nodes via specific edges.
3.  **Data Properties (`onto_data_properties`):** The strict attribute schema for each node type.

This pre-computation ensures that downstream validation processes in BigQuery can perform simple, highly performant relational joins against these rules, rather than executing expensive recursive queries or requiring a dedicated graph database just for schema validation.
