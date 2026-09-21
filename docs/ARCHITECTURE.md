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
                                         ▼
                                  SQLiteRetriever
                                         │
                                         ▼
                                 RequirementContext
                                         │
                                         ▼
                             AnalystModel (OllamaAnalyst)
                                         │
                                         ▼
                                   AnalystResult
                             (identified pattern names)
                                         │
                                         ▼
                                   ContextBuilder ◄─── ObsidianRetriever (via Pattern-Registry.json)
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
- **Responsibility:** Deterministic Python component (`app/retrieval/sqlite_retriever.py`) that queries canonical SRS requirement contexts (`RequirementContext`), metadata, and sections directly from `srs_canonical.db`.
- **Key Principles:** Preserves canonical raw requirement text character-for-character without inference.

### 7. Analyst Model (`AnalystModel` & `OllamaAnalyst`) (IMPLEMENTED)
- **Responsibility:** Pluggable AI layer (`app/analyst/`) analyzing `RequirementContext` instances using local Llama 3 via Ollama (`OllamaAnalyst`) to classify structural engineering patterns.
- **Key Principles:**
  - Pluggable abstract base class interface (`AnalystModel(ABC)`).
  - Uses fixed, versioned prompt architecture (`ANALYST_SYSTEM_PROMPT`).
  - Loads canonical pattern names dynamically from `SRS-Knowledge/Index/Pattern-Registry.json`.
  - Strictly validates output schema (`AnalystResult`), verifying requirement identity matching, pattern uniqueness, and exact pattern name matching against the catalog (raises `NonCanonicalPatternError` for unrecognized patterns).
  - Does NOT perform final formalization or code generation.

### 8. Obsidian Knowledge Retrieval Layer (`ObsidianRetriever`) (IMPLEMENTED)
- **Responsibility:** Deterministic Python component (`app/retrieval/obsidian_retriever.py`) that loads engineering, domain, and formalization knowledge from `SRS-Knowledge/`.
- **Key Principles:**
  - Obsidian is treated strictly as a filesystem-based Markdown knowledge repository.
  - Python does not communicate with the Obsidian GUI or application process.
  - `Pattern-Registry.json` serves as the deterministic routing layer contract.
  - Analyst pattern names are exact registry keys (no fuzzy matching).

### 9. Context Builder (`ContextBuilder` & `ContextPackage`) (IMPLEMENTED)
- **Responsibility:** Deterministic orchestrator (`app/retrieval/context_builder.py`) combining `SQLiteRetriever` and `ObsidianRetriever` outputs into a structured `ContextPackage`.
- **Key Principles:**
  - Preserves requirement input ordering and pattern input ordering.
  - Accepts `AnalystResult.identified_patterns` to build the complete `ContextPackage`.
  - Maintains explicit, inspectable provenance tracking for SQLite databases/tables and Obsidian relative file paths.

### 10. Reasoning Model (PLANNED)
- **Responsibility:** Swappable plugin. Translates `ContextPackage` data into mathematical logic specifications (LTL, predicates).

### 11. Critic Model & Clarification Manager (PLANNED)
- **Responsibility:** Swappable plugin and control loop for verifying mathematical formalizations and managing interactive user clarification dialogues.

---

## 3. Implemented & Planned Model Plugin Interfaces

To make the AI layers interchangeable, the project defines Python Abstract Base Classes (ABCs). Models can be swapped between local APIs, cloud services, or mocks without affecting the orchestrator or retrieval layer.

### Implemented Analyst Model Interface (`app/analyst/analyst_model.py`)
```python
class AnalystModel(ABC):
    @abstractmethod
    def analyze(self, requirement_context: RequirementContext) -> AnalystResult:
        """Analyze a RequirementContext and return a validated AnalystResult."""
        pass
```
- **Ollama implementation:** [`OllamaAnalyst`](file:///c:/Users/PC/Documents/GitHub/SRS-Formalization-Agent/app/analyst/ollama_analyst.py) using `llama3:latest` and JSON mode.
- **Mock implementation:** Used in [`tests/test_analyst_model.py`](file:///c:/Users/PC/Documents/GitHub/SRS-Formalization-Agent/tests/test_analyst_model.py) for fast, offline deterministic testing.

### Planned Reasoning Model Interface (Planned for Milestone 4)
```python
class AbstractReasoningModel(ABC):
    @abstractmethod
    def formalize_requirements(self, context_package: ContextPackage) -> str:
        """Translate ContextPackage into formal specifications (LTL, predicates)."""
        pass
```

