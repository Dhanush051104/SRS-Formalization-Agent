# SRS Formalization Agent

The **SRS Formalization Agent** is a research and prototyping platform designed to ingest natural-language Software Requirements Specifications (SRS) documents and translate their requirements into mathematical logic specifications (e.g., predicates, constraints, and LTL temporal logic). 

This repository currently implements the core **deterministic document parsing, structuring, database indexing, and target group selection layers** (Milestones 1 & 2), preparing the system for integration with future AI Analyst and Reasoning models.

---

## 1. Architectural Concept & Status

### Core Architectural Principle
To maintain traceability and validation integrity, the system divides execution into:
* **Deterministic Document Foundation:** Parser, structurer, and SQLite index are 100% deterministic, preserving exact source elements, sections, and pages.
* **Probabilistic Reasoning plugins:** AI models responsible for analyzing context and generating formal specifications are designed as **swappable plugins** using Python Abstract Base Classes (ABCs).

This design ensures that the model backend (local APIs, remote GPUs, or different providers) can be swapped without changing any core application code.

### Status of Milestones
* **[COMPLETED] Milestone 1: Ingestion & Canonical SQLite Store:** Lossless extraction of document text elements, section structural hierarchy tree, and Section Browser web UI.
* **[COMPLETED] Milestone 2: Target Requirement / Target Group:** Selection and grouping of canonical requirements to form a boundary target for reasoning, validating unique section bounds and document constraints.
* **[IN PROGRESS] Milestone 3: Python Orchestrator & Swappable Plugins:** Interface designs for swappable models (`AnalystModel`, `ReasoningModel`) and orchestration workflow loops.

---

## 2. Repository Structure

```text
SRS-Formalization-Agent/
├── app/                        # Application source code
│   ├── db/                     # Canonical store and Target Group service layer
│   │   ├── canonical_store.py  # SQLite schema initialization and storage
│   │   └── target_service.py   # Target group CRUD operations and validations
│   ├── parser/                 # Document parsing module (PDF/DOCX extraction)
│   │   └── document_parser.py  # Lossless text element parser
│   ├── structurer/             # Structural organization module
│   │   ├── document_cleaner.py # Cleans/normalizes text
│   │   ├── document_structurer.py# Builds section tree and maps requirements
│   │   └── requirement_segmenter.py# Reconstructs multi-element requirements
│   └── ui/                     # Flask presentation layer
│       ├── templates/          # HTML view templates
│       └── app.py              # Flask server routes and page rendering
├── data/                       # Ingestible document samples
│   └── nasaX38 SRS.pdf         # Sample NASA X-38 SRS Document
├── docs/                       # Detailed onboarding documentation
│   ├── ARCHITECTURE.md         # Detailed layer responsibilities and ABC interfaces
│   ├── DATABASE.md             # Schema details and database query guides
│   ├── MILESTONES.md           # Progress history and future roadmap
│   ├── PROJECT_STATUS.md       # High-level goals and status summary
│   └── SETUP.md                # Quick developer configuration guide
├── tests/                      # Testing module
│   ├── test_milestone1.py      # Milestone 1 validation tests
│   ├── test_parser.py          # Ingestion parser diagnostic test
│   ├── test_section_isolation.py# Section isolate boundary tests
│   └── test_target_groups.py   # Target group unit tests
├── requirements.txt            # Project python dependencies
├── run_ui.py                   # UI server startup script
└── srs_canonical.db            # Production SQLite database file
```

---

## 3. Installation & Setup

### Prerequisites
* **Python 3.10+** (Python 3.14 compatible)
* **Windows PowerShell** terminal environment

### Virtual Environment & Dependencies Configuration
Open Windows PowerShell, clone the repository, create a virtual environment, and install dependencies:

```powershell
# 1. Navigate into repository
cd SRS-Formalization-Agent

# 2. Create virtual environment
python -m venv .venv

# 3. Activate virtual environment
.venv\Scripts\Activate.ps1

# 4. Upgrade pip and install requirements
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Verify that packages are installed successfully by executing:
```powershell
pip show Flask pypdf python-docx
```

---

## 4. Running the Tests

To prevent path errors (`ModuleNotFoundError`), **always execute tests from the project root directory** using the `python -m` flag.

### 1. Ingestion Parser Diagnostic Script
Parses the document and displays the Section 3 hierarchy in the console:
```powershell
python -m tests.test_parser
```

### 2. Milestone 1 Core Validation Tests
Tests lossless ingestion, document reconstruction, requirement mappings, and numbering:
```powershell
python -m tests.test_milestone1
```

### 3. Section Isolation Tests
Tests section isolation boundaries (ensuring adjacent content does not bleed into the view):
```powershell
python -m unittest tests/test_section_isolation.py
```

### 4. Target Group Tests
Tests service validations, selection ordering, database UNIQUE constraints, and CRUD features:
```powershell
python -m unittest tests/test_target_groups.py
```

---

## 5. Running the Web UI & Database Details

Start the Flask server:
```powershell
python run_ui.py
```

Open your browser and navigate to: `http://127.0.0.1:5000/`

* **Database File:** On startup, the SQLite database is created/accessed at `srs_canonical.db` in the repository root.
* **Database Inspection:** Because the database remains tracked in Git to preserve the parsed NASA X-38 SRS, you can query it via terminal CLI (`sqlite3 srs_canonical.db`) or browse it visually using **DB Browser for SQLite** (DB4S). See [`docs/DATABASE.md`](file:///c:/Users/PC/Documents/GitHub/SRS-Formalization-Agent/docs/DATABASE.md) for query examples.

---

## 6. Detailed Project Onboarding Documents

Please refer to the following files in the `docs/` folder for deeper onboarding reading:
1. [**Project Status Overview** (`docs/PROJECT_STATUS.md`)](file:///c:/Users/PC/Documents/GitHub/SRS-Formalization-Agent/docs/PROJECT_STATUS.md) — Main executive summary, validation metrics, and model swap strategy.
2. [**Architecture Guide** (`docs/ARCHITECTURE.md`)](file:///c:/Users/PC/Documents/GitHub/SRS-Formalization-Agent/docs/ARCHITECTURE.md) — Technical details of layer responsibilities and ABC plugin class code definitions.
3. [**Setup and Execution** (`docs/SETUP.md`)](file:///c:/Users/PC/Documents/GitHub/SRS-Formalization-Agent/docs/SETUP.md) — PowerShell setup instructions, test commands, outputs, and troubleshooting.
4. [**Database Documentation** (`docs/DATABASE.md`)](file:///c:/Users/PC/Documents/GitHub/SRS-Formalization-Agent/docs/DATABASE.md) — Schema layers, columns, constraints, and inspector guides.
5. [**Milestone History** (`docs/MILESTONES.md`)](file:///c:/Users/PC/Documents/GitHub/SRS-Formalization-Agent/docs/MILESTONES.md) — Active roadmap and completed milestones.