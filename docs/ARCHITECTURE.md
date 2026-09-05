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
                    Target Requirement / Target Group
                                   │
                         ┌─────────┴─────────┐
                         ▼                   ▼
                  SQLiteRetriever     ObsidianRetriever
                         │                   │
                         └─────────┬─────────┘
                                   ▼
                            ContextBuilder
                                   │
                                   ▼
                            ContextPackage
                                   │
                                   ▼
                           Future Reasoning Model
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

### 6. SQLite Retriever (`SQLiteRetriever`) (IMPLEMENTED)
- **Responsibility:** Deterministic Python component (`app/retrieval/sqlite_retriever.py`) that queries canonical SRS requirement contexts, metadata, and sections directly from `srs_canonical.db`.
- **Key Principles:** Preserves canonical raw requirement text character-for-character without inference.

### 7. Obsidian Knowledge Retrieval Layer (`ObsidianRetriever`) (IMPLEMENTED)
- **Responsibility:** Deterministic Python component (`app/retrieval/obsidian_retriever.py`) that loads engineering, domain, and formalization knowledge from `SRS-Knowledge/`.
- **Key Principles:**
  - Obsidian is treated strictly as a filesystem-based Markdown knowledge repository.
  - Python does not communicate with the Obsidian GUI or application process.
  - `Pattern-Registry.json` serves as the deterministic routing layer contract.
  - Analyst pattern names are exact registry keys (no fuzzy matching).

### 8. Context Builder (`ContextBuilder` & `ContextPackage`) (IMPLEMENTED)
- **Responsibility:** Deterministic orchestrator (`app/retrieval/context_builder.py`) combining `SQLiteRetriever` and `ObsidianRetriever` outputs into a structured `ContextPackage`.
- **Key Principles:**
  - Preserves requirement input ordering and pattern input ordering.
  - Maintains explicit, inspectable provenance tracking for SQLite databases/tables and Obsidian relative file paths.
  - Does NOT contain low-level SQLite queries or Markdown parsing logic.
  - Does NOT perform requirement interpretation, LLM prompting, or formalization generation.

### 9. Python Orchestrator (IN PROGRESS)
- **Responsibility:** Runs the core loop. It accepts a target group, invokes `ContextBuilder`, manages history, calls model plugins, and drives the workflow.

### 10. Analyst Model (PLANNED)
- **Responsibility:** Swappable plugin. Analyzes target requirements and identifies applicable pattern names.

### 11. Reasoning Model (PLANNED)
- **Responsibility:** Swappable plugin. Translates `ContextPackage` data into mathematical logic specifications (LTL, predicates).

### 11. Output (PLANNED)
- **Responsibility:** Exports the validated formalization (e.g., JSON schemas, TLA+ specifications, or logic files).

---

## 3. Planned Model Plugin Interfaces (Planned for Milestone 3)

To make the AI layers interchangeable in the future, the project will define Python Abstract Base Classes (ABCs). Models will be swapped between local APIs, cloud services, or mocks without affecting the orchestrator.

> [!NOTE]
> The interfaces below are **planned architectural examples** and are not yet defined in the Python codebase. They will be introduced in Milestone 3.

### Planned Analyst Model Interface Example
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

### Planned Reasoning Model Interface Example
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
