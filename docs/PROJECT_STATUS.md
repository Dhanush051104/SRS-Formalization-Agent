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

### Milestone 2: Target Requirement / Target Group Layer
We implemented the boundary between the canonical SQLite database and future AI reasoning components.
- **Target Selection:** Users can select one or multiple requirements from any section via the UI and bundle them into a **Target Group**.
- **Referential Integrity:** The target group references canonical requirements in SQLite using foreign keys rather than copying text. Uniqueness constraints (`UNIQUE(target_group_id, requirement_id)`) are enforced.
- **Traceability Chain:** Full traceability is preserved from target group $\rightarrow$ requirement ID $\rightarrow$ SRS ID $\rightarrow$ section $\rightarrow$ page $\rightarrow$ canonical raw elements.
- **Deterministic Service Layer:** Validations guarantee that a target group only contains unique requirements belonging to the same document and same section, and that all inputs are valid.

---

## 4. Current Ingestion and Validation Results
Based on testing against the **NASA X-38 Software Requirements Specification (SRS)**:
* **Parsed Raw Elements:** 5,379 elements ingested.
* **Unique Requirements Detected:** 195 SRS requirements.
* **Real Sections Identified:** 107 sections (including Sections 1 and 2, which are represented in the tree even with 0 requirements).
* **Section 3.2.1 System Initialization:** Confirmed to contain all 17 requirements (R1 to R17 / SRS194 to SRS015).
* **Target Group Test Suite:** 13 unit tests verifying validations, selection order, and CRUD operations pass successfully.

---

## 5. What Is Being Worked On Next (Milestone 3)
We are currently entering the **pre-Analyst Orchestration Layer** phase:
1. **Model-Plugin Interfaces:** Designing Python abstract base classes for the swappable `AnalystModel` and `ReasoningModel`.
2. **Orchestrator backbone:** Building the control loop that receives a Target Group, queries related context/definitions from SQLite, prepares the model prompts, and runs validation on model outputs.

No LLM, reasoning models, or formalization routines are implemented in the main repository yet.

---

## 6. Remote GPU & Swappable Hardware Strategy
During development and deployment, we want to run large open-source formalization models (like DeepSeek-Coder, Llama-3, or specialized fine-tuned reasoning models). 

Because local developer machines may have limited GPU hardware (RAM/VRAM), we are designing the orchestrator to support a **hybrid deployment strategy**:
* **Remote Dev Environment:** The Python orchestrator runs locally, calling remote GPU instances (e.g., RunPod, Vast.ai) hosting model APIs during the developer phase.
* **Local Production Environment:** Once deployed on target developer workstations with high-capacity hardware, the orchestrator connects to local models (e.g., Ollama or local Hugging Face pipelines) using the same model-plugin interfaces.
