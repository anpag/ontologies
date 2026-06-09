# Semantic "Clean Room" Architecture

## The Challenge: Dirty Data & Strict Ontologies
In real-world enterprise deployments, unstructured text and spreadsheet data are inherently "dirty." They contain:
- **Synonyms & Aliases:** e.g., "THF", "oxolane", and "Tetrahydrofuran" all refer to the same chemical.
- **Missing or Implicit Units:** e.g., A spreadsheet cell contains "10" without specifying "ml", or textual data says "10 mls" instead of the standard unit.

If we ask an LLM to simultaneously extract data *and* normalize it to a rigid ontology (e.g., mapping "mls" to the QUDT URI `[qudt:MilliL]`), performance degrades significantly. The LLM is forced to guess, leading to hallucinations and the injection of silent errors into the production Property Graph.

## The Solution: Decoupling Extraction and Canonicalization
To ensure data integrity, we introduce a Semantic "Clean Room" stage that separates raw extraction from semantic normalization.

### Stage 1: Raw Extraction (The "Dirty" Agent)
A programmatic Vertex AI Python SDK Agent reads the unstructured document (PDF, TXT, etc.). Its prompt instructs it to extract **exactly** what is written in the text, without attempting to map it to official ontology URIs or standard units.
*   **Input text:** `Used 10 mls of THF.`
*   **Output JSON:** `{"entity": "THF", "value": 10, "raw_unit": "mls"}`

*Note: Any tacit knowledge, insights, or risks that cannot be represented as structured triples are safely extracted into an `unbound_knowledge` array.*

### Stage 2: The Clean Room (BigQuery Staging)
The raw output lands in a BigQuery staging area. A Dataform pipeline processes this data using a two-pronged approach:

1. **Deterministic Dictionary Lookup (SKOS & QUDT):**
   BigQuery performs strict relational `JOIN`s against materialized reference tables imported from standard W3C frameworks:
   - **SKOS (Simple Knowledge Organization System):** Used to map synonyms. `"THF"` (`skos:altLabel`) is deterministically mapped to the canonical `[henkel:Tetrahydrofuran]` (`skos:prefLabel`).
   - **QUDT (Quantities, Units, Dimensions, and Data Types):** Used to normalize metrology. `"mls"` is mapped to `[qudt:MilliL]`.

2. **Agentic Inference (The "Data Janitor"):**
   If data is incomplete (e.g., a missing unit of measurement like `"10"`), the pipeline flags the row. A specialized "Data Janitor" LLM Agent is invoked. Its sole responsibility is to analyze the isolated context of that specific field and infer the missing data. 
   - *Example:* "Given this column is for atmospheric pressure, the value '10' must be '10 atm'."

### Stage 3: Human-in-the-Loop (HITL) & Dead Letter Queue (DLQ)
If the deterministic lookup fails AND the Data Janitor Agent's confidence score is below a strict threshold (e.g., 95%), the data is **prevented** from entering the production graph.
Instead, it is routed to a BigQuery Dead Letter Queue (`dlq_semantic_failures`). 

A human domain expert reviews the anomaly and manually maps it to the correct canonical entity or unit. 
**Crucially, this manual mapping is written back into the core Ontology's SKOS `altLabel` definitions.** This creates a feedback loop: the system learns the new synonym, ensuring the same anomaly is handled automatically in the future.
