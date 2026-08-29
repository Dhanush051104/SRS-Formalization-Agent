# System Architecture: SRS Formalization Agent

This document details the system architecture of the SRS Formalization Agent. It outlines the responsibilities of each layer, the separation of deterministic and probabilistic stages, and the design of swappable model plugins.

---

## 1. Architectural Design Principles

The architecture is built on a key engineering constraint:
> **Deterministic document processing must remain separate from probabilistic model reasoning.**

Natural-language documents contain formatting, sections, and paragraphs that can be parsed and indexed with 100% precision. Conversely, reasoning about requirement definitions, consistency, and formalization involves probabilistic models (LLMs). Mixing these two stages directly in the parsing or database layer causes loss of traceability and makes the system fragile.

To maintain integrity, the system divides execution into a **deterministic foundation layer** (SQLite and Python orchestrator) and a **probabilistic analysis layer** (Model Plugins).

---

## 2. Layer-by-Layer Responsibilities

```
    +-------------------------------------------+
    |               User / Web UI               |
    +-------------------------------------------+
                          |
                          v
    +-------------------------------------------+
    |              Document Parser              | (Deterministic)
    +-------------------------------------------+
                          |
                          v
    +-------------------------------------------+
    |            Document Structurer            | (Deterministic)
    +-------------------------------------------+
                          |
                          v
    +-------------------------------------------+
    |          SQLite Canonical Store           | (Deterministic)
    +-------------------------------------------+
                          |
                          v
    +-------------------------------------------+
    |        Target Requirement / Group         | (Deterministic Boundary)
    +-------------------------------------------+
                          |
                          v
    +-------------------------------------------+
    |            Python Orchestrator            | (Control Loop)
    +-------------------------------------------+
                          |
       +------------------+------------------+
       |                                     |
       v                                     v
+-------------+                       +-------------+
|   Analyst   | (Probabilistic)       |  Reasoning  | (Probabilistic)
|    Plugin   |                       |    Plugin   |
+-------------+                       +-------------+
```

### 1. Document Parser (IMPLEMENTED)
- **Responsibility:** Ingests raw source documents (PDF/DOCX) and converts them into a flat list of text elements, retaining page metadata, type (text, table, lists), and styles.
- **Traceability:** Assigns an index (`element_index`) to every parsed snippet to maintain source ordering.

### 2. Document Structurer (IMPLEMENTED)
- **Responsibility:** 
  - Segmenter: Reconstructs contiguous requirement sentences spanning multiple lines/elements and links them to their unique `[SRSxxx]` tag.
  - Structurer: Scans the document, identifies genuine section headings, builds a tree hierarchy of parents/children, and maps requirements to their parent sections.
- **Traceability:** Preserves both section parent-child chains and requirement-to-section links.

### 3. SQLite Canonical Store (IMPLEMENTED)
- **Responsibility:** Serves as the canonical source of truth (`srs_canonical.db`). It stores documents, pages, raw elements, sections, and requirements.
- **Traceability:** Prevents data loss; allows recreating the original document in source order.

### 4. Section / Knowledge Index (IMPLEMENTED)
- **Responsibility:** Reconstructs isolated section boundaries. When a section is loaded, it extracts only elements and requirements belonging to that section's boundary, skipping headers, cover pages, and sibling contents.

### 5. Target Requirement / Target Group (IMPLEMENTED)
- **Responsibility:** Provides the UI and service boundary where developers or users select specific requirements to form an analysis target.
- **Traceability:** Enforces database uniqueness constraints, validates selection parameters, and maps group membership back to canonical requirements.

### 6. Python Orchestrator (IN PROGRESS)
- **Responsibility:** Runs the core loop. It accepts a target group, fetches the required context and dependencies from SQLite, manages history, calls the plugins, and drives the workflow.

### 7. Analyst Model (PLANNED)
- **Responsibility:** Swappable plugin. Analyzes the target requirements, determines external dependencies (e.g., helper functions, variables defined in other sections), and requests the orchestrator to retrieve context.

### 8. Retrieval / Context Manager (PLANNED)
- **Responsibility:** Fetches the extra contextual information requested by the Analyst Model from the SQLite index and appends it to the prompt history.

### 9. Reasoning Model (PLANNED)
- **Responsibility:** Swappable plugin. Translates the target requirement and its gathered context into mathematical logic representations (LTL, predicates).

### 10. Classification / Validation (PLANNED)
- **Responsibility:** Compiles and validates the generated formalization against the expected syntax, checking for contradictions or parsing errors.

### 11. Output (PLANNED)
- **Responsibility:** Exports the validated formalization (e.g., JSON schemas, TLA+ specifications, or logic files).

---

## 3. Swap-Ready Model Plugin Interfaces

To make the AI layers interchangeable, the project uses Abstract Base Classes (ABCs) in Python. Models can be swapped between local APIs, cloud services, or mocks without affecting the orchestrator.

### Analyst Model Interface
```python
class AbstractAnalystModel:
    def analyze_requirements(self, target_requirements: list[dict], context: dict) -> dict:
        """
        Analyze requirements to determine needed context, variables, and dependencies.
        """
        raise NotImplementedError
```
- **Local implementation:** Calls a local model running in Ollama or Hugging Face.
- **Remote implementation:** Queries a cloud GPU provider (e.g. Vast.ai, RunPod, or a standard LLM endpoint).
- **Mock implementation:** Returns hardcoded dependencies for validation tests.

### Reasoning Model Interface
```python
class AbstractReasoningModel:
    def formalize_requirements(self, target_requirements: list[dict], context: dict) -> str:
        """
        Translate requirements and context into formal specifications.
        """
        raise NotImplementedError
```
- **Local implementation:** Runs a local reasoning LLM model.
- **Remote implementation:** Calls a remote GPU reasoning endpoint.
- **Mock implementation:** Returns pre-defined LTL statements for unit testing.
