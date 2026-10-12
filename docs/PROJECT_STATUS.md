# Project Status: SRS Formalization Agent

This document provides a high-level status report of the SRS Formalization Agent project. It is intended for project directors, onboarding developers, and other stakeholders who want to understand what has been completed, what is in progress, and the overall architectural direction.

---

## 1. Project Objectives
The **SRS Formalization Agent** is a research and prototyping system designed to ingest Software Requirements Specification (SRS) documents and translate their natural-language requirements into structured mathematical representations, predicates, and temporal logic (e.g., LTL). 

This formalization enables automated verification, consistency checks, and safety analysis of critical software systems before implementation.

---

## 2. Overall Architectural Concept
The core design philosophy is: **deterministic document processing must remain separate from probabilistic model reasoning**. 

The Python orchestration layer acts as the backbone, driving the workflow and managing the context database. The AI models—responsible for analyzing context and generating formal specifications—are treated as **swappable plugins**. This ensures the system can easily support different models (local or cloud-hosted) without redesigning the core ingestion, parsing, database, or UI layers.

---

## 3. What Has Been Completed

### Milestone 1: Whole-SRS Lossless Ingestion & SQLite Canonical Store
We built a parsing pipeline that extracts every text element from the source document (supporting PDF and DOCX) and preserves them in a local SQLite database (`srs_canonical.db`).
- **Lossless Ingestion:** Explanatory text, section headings, requirements, and formatting elements are captured. The raw source remains structured so the document can be reconstructed in its original source order.
- **Section Structuring:** The document structure is parsed sequentially, mapping sections and sub-sections (e.g., `3.2.1`) while filtering out lists and numbered requirement sentences to avoid fake sections.
- **Traceability:** Requirements (identified by numbered statements containing `[SRSxxx]` tags) are parsed, keeping their original section, page number, raw text, and source element order.
- **Interactive Section Browser:** An interactive Flask web UI allows users to view the parsed document section-by-section, check requirement counts, and read reconstructed source content.

### Milestone 6: Bounded Automated Revision Loop
We implemented the `RevisionManager` orchestrating bounded iterative feedback cycles between `ReasoningModel` and `CriticModel`.
- **Bounded Automated Loop:** Orchestrates `ReasoningModel.reason()` $\rightarrow$ `CriticModel.critique()` $\rightarrow$ check status $\rightarrow$ retry with structured Critic feedback prompt if `NEEDS_REVISION` up to `max_iterations` (default 3).
- **Termination Safeguards:** Immediately halts loop on `PASS` (status=`PASS`, `CRITIC_PASSED`) or `BLOCKED` (status=`BLOCKED`, `CRITIC_BLOCKED`). Sets status=`MAX_ITERATIONS` (`MAX_ITERATIONS_REACHED`) if limit is hit without forcing `PASS`.
- **Full History Provenance:** Captures every intermediate `ReasoningResult`, `CriticResult`, and revision prompt in `RevisionHistoryEntry` inside `RevisionResult`.
- **Forwarding Feedback:** `build_revision_user_prompt` serializes original `ContextPackage`, candidate formalization, and full Critic findings (severities, descriptions, source/reasoning evidence, recommendations, missing constraints, unsupported assumptions) into the revision prompt.

### Milestone 7: Symbol Registry, Retrieval & Validation
We implemented the canonical Symbol Registry infrastructure ([app/symbols/](file:///c:/Users/PC/Documents/GitHub/SRS-Formalization-Agent/app/symbols/)) and authoritative registry file ([data/symbol_registry.json](file:///c:/Users/PC/Documents/GitHub/SRS-Formalization-Agent/data/symbol_registry.json)).
- **Authoritative Registry:** Canonical repository defining mathematical logic operators, temporal operators, propositional connectives, and requirement-scoped domain predicates/constants. Prevents models from silently redefining symbols.
- **Scope Isolation:** Separates globally applicable symbols (`G`, `F`, `X`, `U`, `->`, `&&`, etc.) from requirement-scoped symbols (e.g. `loss_of_comm`, `outputs_disabled` scoped strictly to `[SRS178]`). Allows legitimate distinct definitions across different requirement scopes.
- **Deterministic Validation:** Validates unique identifiers, detects duplicate spellings or alias collisions within identical scopes, and rejects malformed registry entries.
- **Deterministic Retrieval:** `SymbolRetriever` provides queries for global symbols, requirement-relevant symbols, category searches, and spelling/alias lookups with explicit provenance.
- **Consistency Validator:** `SymbolValidator` audits candidate formalizations against registry definitions, flagging out-of-scope symbol leaks, conflicting definitions, and unregistered domain identifiers.
- **Additive Context Integration:** `ContextBuilder.build()` provides an additive `include_symbols=True` flag to inject symbols into `ContextPackage.symbols` without breaking existing callers or backward compatibility.

### Evaluation Fixture: Multi-Domain Simple Requirements Corpus
Integrated a dedicated 306-requirement multi-domain evaluation corpus ([tests/fixtures/simple_requirements.txt](file:///c:/Users/PC/Documents/GitHub/SRS-Formalization-Agent/tests/fixtures/simple_requirements.txt)) and a lightweight structured loader ([tests/fixtures/simple_requirements_loader.py](file:///c:/Users/PC/Documents/GitHub/SRS-Formalization-Agent/tests/fixtures/simple_requirements_loader.py)).
- **Corpus Coverage:** 306 natural-language requirements across 10 engineering domains (redundant computer / bus-master system, ventilator, UAV, washing machine, microwave oven, refrigerator, ADAS, fire safety controller, access control, elevator).
- **Architecture Integrity:** Kept strictly separate from the production SRS knowledge base (`SRS-Knowledge/`) without modifying pattern or concept notes.
- **Intended Purpose:** Serves as a standardized benchmark corpus for:
  1. **Module-level testing:** Validating individual prompt schemas, parser stages, and model output mappings.
  2. **Regression testing:** Preventing performance degradation across system updates.
  3. **Final end-to-end evaluation:** Verifying end-to-end pipeline execution from requirement selection to final formalization.
  4. **Pattern coverage evaluation:** Assessing how effectively identified patterns map across diverse system domains.
  5. **Model-quality benchmarking:** Comparing formalization accuracy, precision, and hallucination rates across different LLM backends (Llama 3, DeepSeek, Claude, GPT-4).

---

## 4. Current Ingestion and Validation Results
Based on testing against the **NASA X-38 Software Requirements Specification (SRS)** and the **Simple Requirements Corpus**:
* **Parsed Raw Elements:** 5,379 elements ingested.
* **Unique Requirements Detected:** 195 SRS requirements (NASA X-38) + 306 Multi-Domain Evaluation requirements.
* **Real Sections Identified:** 107 sections (including Sections 1 and 2, which are represented in the tree even with 0 requirements).
* **Section 3.2.1 System Initialization:** Confirmed to contain all 17 requirements (R1 to R17 / SRS194 to SRS015).
* **Target Group Test Suite:** 13 unit tests verifying validations, selection order, and CRUD operations pass successfully.
* **Evaluation Corpus Test Suite:** 7 deterministic unit tests verifying exact line preservation, 1-306 numbering, domain categorization, and duplicate separation pass cleanly.
* **Symbol Registry Test Suite:** 16 deterministic unit tests verifying loading, global/scoped retrieval, alias resolution, scope isolation, validation rejection, and formalization auditing pass cleanly.
* **Full Agent Test Suite:** 119 offline deterministic unit tests + live Ollama Llama 3 integration tests pass cleanly.

---

## 5. What Is Being Worked On Next (Milestone 7)
We are currently entering the **Clarification Manager & Interactive UI Loop** phase:
1. **Clarification Manager:** Managing interactive clarification dialogues when the Critic or Reasoning Model flags unstated parameters or un-resolvable ambiguities under `unresolved_items` or `BLOCKED` status.
2. **Flask Web UI Integration:** Exposing the complete end-to-end trace (Requirement $\rightarrow$ Analyst $\rightarrow$ Obsidian Knowledge $\rightarrow$ Reasoning Formalization $\rightarrow$ Critic Evaluation $\rightarrow$ Revision Iteration History) in the interactive web interface.

---

## 6. Remote GPU & Swappable Hardware Strategy
During development and deployment, we want to run large open-source formalization models (like DeepSeek-Coder, Llama-3, or specialized fine-tuned reasoning models). 

Because local developer machines may have limited GPU hardware (RAM/VRAM), we are designing the orchestrator to support a **hybrid deployment strategy**:
* **Remote Dev Environment:** The Python orchestrator runs locally, calling remote GPU instances (e.g., RunPod, Vast.ai) hosting model APIs during the developer phase.
* **Local Production Environment:** Once deployed on target developer workstations with high-capacity hardware, the orchestrator connects to local models (e.g., Ollama or local Hugging Face pipelines) using the same model-plugin interfaces.

