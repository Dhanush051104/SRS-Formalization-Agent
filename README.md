# SRS Formalization Agent

The **SRS Formalization Agent** is an engineering AI platform designed to ingest natural-language Software Requirements Specifications (SRS) documents and translate their requirements into mathematical logic specifications (predicates, constraints, and LTL temporal logic).

The platform pairs a deterministic document ingestion and knowledge retrieval foundation with local AI models (via Ollama) orchestrated through a bounded revision loop, deterministic structural & symbol validators, and an interactive stakeholder clarification manager.

---

## 1. Architectural Concept & Subsystems

```
Document Ingestion (PDF/DOCX)
          ↓
Canonical SQLite Store (`srs_canonical.db`)
          ↓
Requirement Selection & Target Groups
          ↓
Analyst Model (Identifies structural patterns: Invariant, Periodic, Timeout, etc.)
          ↓
ContextBuilder (Retrieves Obsidian Vault notes + Canonical Symbol Registry)
          ↓
Reasoning Model (Synthesizes candidate LTL formulas, predicates, constraints)
          ↓
Critic Model & Structural/Symbol Validators (Independent audit of correctness & scoping)
          ↓
RevisionManager (Bounded feedback revision loop)
          ↓
ClarificationManager (Deterministic question synthesis & answer persistence)
          ↓
Result Store (`data/result_cache.json`)
          ↓
Flask Web UI (Full View formalization dashboard, batch runner, model config)
```

### Core Design Principles
* **Deterministic Foundation:** Document parsing, structuring, SQLite storage, Obsidian retrieval, symbol scoping, and clarification tracking are 100% deterministic, maintaining complete traceability and provenance.
* **Authoritative Symbol Registry:** Mathematical, temporal, and requirement-scoped domain symbols are strictly governed by `data/symbol_registry.json`. Models cannot silently redefine symbols.
* **Defense-in-Depth Validation:** Structural grammar validation and deterministic symbol scope auditing prevent formulas from passing when syntax is broken or symbols leak across scopes.
* **Interactive Clarification Loop:** Unresolved parameters and Critic findings synthesize structured stakeholder questions with selectable options and custom text inputs. Recorded resolutions persist across runs and inform subsequent reasoning passes.
* **Zero Production Mocks:** Production code executes real pipeline components without synthetic fast-paths.

---

## 2. Repository Structure

```text
SRS-Formalization-Agent/
├── app/                        # Application source code
│   ├── analyst/                # Analyst pattern identification models
│   ├── clarification/          # Clarification manager, questions, and schemas
│   ├── critic/                 # Independent Critic validation models & findings
│   ├── db/                     # Canonical store and Target Group service layer
│   │   ├── canonical_store.py  # SQLite schema initialization and storage
│   │   └── target_service.py   # Target group CRUD operations and validations
│   ├── formalization_validator.py # Deterministic LTL syntax & structure validator
│   ├── parser/                 # Document parsing module (PDF/DOCX extraction)
│   ├── pipeline.py             # Master orchestrator coordinating all pipeline stages
│   ├── reasoning/              # Reasoning formalization models & prompt builders
│   ├── retrieval/              # SQLite & Obsidian vault knowledge retrievers
│   ├── revision/               # Bounded iterative revision manager
│   ├── structurer/             # Document hierarchy builder & requirement segmenter
│   ├── symbols/                # Authoritative Symbol Registry, Retriever & Validator
│   └── ui/                     # Flask presentation layer
│       ├── model_config.py     # Local model configuration persistence
│       ├── result_store.py     # Atomic persistent cache for pipeline results
│       ├── templates/          # HTML view templates
│       └── app.py              # Flask server routes and page rendering
├── data/                       # Reference documents, registry, and caches
│   ├── nasaX38 SRS.pdf         # Sample NASA X-38 SRS Document
│   ├── symbol_registry.json    # Canonical Authoritative Symbol Registry
│   └── result_cache.json       # Persistent formalization results cache
├── docs/                       # Project documentation
│   ├── ARCHITECTURE.md         # Detailed layer responsibilities and ABC interfaces
│   ├── DATABASE.md             # Schema details and database query guides
│   ├── MILESTONES.md           # Progress history across Milestones 1 through 9
│   ├── PROJECT_STATUS.md       # Status report, verification metrics, and capabilities
│   └── SETUP.md                # Developer configuration guide
├── SRS-Knowledge/              # Frozen Obsidian knowledge vault (Read-only)
├── tests/                      # Deterministic offline & live integration tests
├── requirements.txt            # Python dependencies
├── run_ui.py                   # UI server startup script
└── srs_canonical.db            # Canonical SQLite database file
```

---

## 3. Installation & Setup

### Prerequisites
* **Python 3.10+** (tested on Python 3.14)
* **Windows PowerShell** (or Bash on Unix)
* **Ollama** (optional, for live model inference; default models: `llama3:latest`, `gemma4:e2b`, `qwen3.5:9b`)

### Virtual Environment & Dependencies
```powershell
# 1. Clone repository and navigate into project directory
cd SRS-Formalization-Agent

# 2. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt
```

---

## 4. Running the Tests

To prevent path issues, always execute test commands from the project root.

### Complete Offline Test Suite (216 tests)
Runs the entire deterministic offline test suite covering all subsystems:
```powershell
python -m unittest tests/test_analyst_model.py tests/test_clarification.py tests/test_context_builder.py tests/test_critic_model.py tests/test_formalization_safety.py tests/test_milestone1.py tests/test_model_settings.py tests/test_obsidian_retriever.py tests/test_parser.py tests/test_pipeline.py tests/test_reasoning_model.py tests/test_revision_manager.py tests/test_section_isolation.py tests/test_simple_requirements.py tests/test_sqlite_retriever.py tests/test_structure_debug.py tests/test_symbol_registry.py tests/test_target_groups.py
```
*Current test status: **216 passed / 216 total (0 failures, 0 errors)** in ~35 seconds.*

### Individual Component Tests
```powershell
# Ingestion and canonical store
python -m unittest tests/test_milestone1.py
python -m unittest tests/test_target_groups.py

# Symbol Registry & Scoping Validation
python -m unittest tests/test_symbol_registry.py

# Clarification Workflow & State Transitions
python -m unittest tests/test_clarification.py

# Pipeline Orchestration, Full View & Batch Routes
python -m unittest tests/test_pipeline.py
```

---

## 5. Running the Web Application

Start the Flask application:
```powershell
python run_ui.py
```
Open a browser and navigate to: `http://127.0.0.1:5000/`

### Key Web Features
- **Document Explorer (`/`):** Browse the hierarchical section tree, view parsed requirements, and see starting section recommendations.
- **Target Groups (`/target_group/<id>`):** Select sets of requirements, manage group membership, and launch batch formalizations.
- **Full View Formalization Dashboard (`/formalize/<id>`):** Inspect mathematical LTL formalizations, deterministic syntax validation reports, natural language interpretations, analyst patterns, canonical symbols, revision history, and interactive stakeholder clarification forms.
- **Batch Formalization (`/formalize/batch`):** Sequentially formalize batches of requirements with real-time status summary badges (`PASS`, `PASS (NEEDS CLARIFICATION)`, `INVALID FORMULA`, `BLOCKED`, `FAILED`).
- **Model Settings (`/settings/models`):** Configure installed Ollama models for Analyst, Reasoning, and Critic roles.