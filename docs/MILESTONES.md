# Chronological Milestone Record

This document records the milestones of the SRS Formalization Agent project, showing what has been delivered, what is active, and the upcoming roadmap.

---

## Completed Milestones

### Milestone 1: Whole-SRS Lossless Ingestion & SQLite Canonical Store
* **Status:** COMPLETED
* **Objective:** Parse a full SRS document (e.g. NASA X-38 PDF) losslessly, store the structure in a structured SQLite database, and view the document section-by-section using a web browser.
* **Key Deliverables:**
  - PDF parser extracting text lines, styles, and page info.
  - Section hierarchy structurer (extracts sections, ignores list numbering to avoid fake sections).
  - Database schema (`documents`, `pages`, `elements`, `sections`, `requirements`).
  - Flask web app for document browser.
  - Test suites verifying element ordering, hierarchy matching, and section boundaries.

### Milestone 2: Target Requirement / Target Group Layer
* **Status:** COMPLETED
* **Objective:** Build a selection and grouping mechanism for requirements to form a boundary target for subsequent AI processing.
* **Key Deliverables:**
  - `target_groups` and `target_group_members` tables.
  - Target selection service with uniqueness constraints and selection-order indexing.
  - UI selection check-boxes, quick single-requirement shortcut, and group summary/management pages.
  - Automated tests validating group operations, validations, and database constraints.

---

## Active & Upcoming Roadmap

### Milestone 3: Python Orchestrator & Swappable Plugin Interfaces
* **Status:** IN PROGRESS
* **Objective:** Define the abstract plugin boundaries for LLMs and construct the orchestrator backbone.
* **Key Deliverables:**
  - Python abstract interfaces (`AbstractAnalystModel`, `AbstractReasoningModel`).
  - Python orchestrator loop executing context extraction and prompt management.
  - Local, Remote (API-based), and Mock plugin setups.

### Milestone 4: Swappable Analyst Model (Model Swapping)
* **Status:** PLANNED
* **Objective:** Connect the orchestrator to an active model (local or remote cloud GPUs like Vast.ai/RunPod) to identify variables and context dependencies.

### Milestone 5: Swappable Reasoning Model & Formalization Pipeline
* **Status:** PLANNED
* **Objective:** Connect to formalization models to translate context-rich requirements into mathematical predicates and temporal logic (LTL).

### Milestone 6: Syntax Verification & Export
* **Status:** PLANNED
* **Objective:** Compile and validate the generated mathematical outputs for syntax errors and export clean formalized logic specifications.
