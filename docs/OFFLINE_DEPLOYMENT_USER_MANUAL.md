# Offline Deployment & User Setup Manual
## SRS Formalization Agent
**DRDO – Aeronautical Development Establishment (ADE)**

---

## 1. Introduction

### 1.1 What the SRS Formalization Agent Does
The **Software Requirements Specification (SRS) Formalization Agent** is an engineering AI assistant developed at ADE. It automates the rigorous translation of natural-language defense software requirements (such as flight-critical avionics specifications) into verifiable mathematical representations (such as Linear Temporal Logic — LTL, state predicates, and timing bounds).

The system works through an automated multi-stage pipeline:
1. **Analyst & Set-Level Stage**: Scans single requirements or batches, matches individual patterns (e.g., *Timeout / Deadline*, *Failure Handling*), and conducts set-level dependency analysis across sections to identify shared entities, cross-references, and producer-consumer relationships.
2. **Context Retrieval**: Deterministically fetches domain concepts, formal grammar templates, and canonical mathematical symbols from a local knowledge vault, and enriches prompts with set-level context.
3. **Reasoning Stage**: Uses a local Large Language Model (LLM) to generate structured intermediate representations (atomic clauses, predicates), candidate mathematical logic, and constraint provenance classifications without hallucinating unstated bounds.
4. **Critic & Verification Stage**: An independent verification model audits the candidate formula against source constraints, timing bounds, and engineering assumptions under strict "no invented numbers" rules.
5. **Deterministic Structural & Symbol Validation**: Algorithmic Python checkers verify that logical operators are syntactically complete and that all symbols conform to the canonical symbol registry. Deterministic findings cannot be overridden by LLM assessments.
6. **Revision Loop**: Automatically revises flawed candidate formulas up to a user-configured limit, preserving answered stakeholder clarifications as binding constraints.
7. **Clarification Manager**: Detects unstated engineering bounds and presents structured questions to human engineers with one-click re-formalization.
8. **Results & History Ledger**: Persists all formalization results and execution runs for auditability without requiring expensive re-computation.

### 1.2 Purpose of this Manual
This manual provides complete, step-by-step instructions for installing, configuring, and operating the SRS Formalization Agent **entirely offline** within an air-gapped, high-security environment at ADE.

It is specifically written so that any officer, scientist, or engineer—even without a computer science background or prior programming experience—can set up and use the tool without external assistance.

### 1.3 Verified Offline Status
- **Core Backend & Inference**: **100% Offline-Capable**. The application runs completely locally using SQLite for data storage, local Markdown files for engineering knowledge, and an on-premise Ollama instance for local LLM inference. It requires **no internet access, no cloud APIs (no OpenAI, no Gemini, no Anthropic), and no external servers**.

### 1.4 Reliability & Traceability Architecture
The agent incorporates four core engineering safeguards designed specifically for safety-critical defense systems:
1. **Constraint Provenance Grounding**: Every parameter, threshold, and timing bound is classified into five formal categories:
   - `EXPLICIT_SOURCE`: Literal facts quoted directly from the requirement text.
   - `SUPPORTED_DEPENDENCY`: Constraints derived from related requirements or section contexts.
   - `APPROVED_DERIVATION`: Constants or rules established through answered stakeholder clarifications or approved domain notes.
   - `UNRESOLVED`: Necessary technical bounds not stated in the source text (flagged for clarification).
   - `UNSUPPORTED`: Hallucinated or unjustified parameters (strictly forbidden).
2. **Prompt De-contamination**: Generic reasoning and critic prompts are completely scrubbed of hardcoded example numbers (such as arbitrary timeouts or resets), preventing cross-requirement parameter contamination.
3. **Set-Level Batch Analysis**: When analyzing a group or section, the system clusters requirements, identifies shared entities and buses, detects cross-references (e.g. `[SRS178]`), and maps producer-consumer links before individual formalization.
4. **Compositional Intermediate Representation**: Formulas are built compositionally from atomic propositions and predicate definitions rather than emitted as monolithic strings, allowing granular inspection in the web dashboard.
- **Browser User Interface (100% Self-Hosted Assets)**: The web interface uses standard HTML templates with bundled, self-hosted Bootstrap 5.3.0 and Bootstrap Icons 1.10.0 stylesheets, scripts, and font files under `app/ui/static/vendor/`. Zero external CDN links or internet network requests are made by the browser. Full styling renders cleanly on fresh, air-gapped computers without needing pre-cached browser files.

---

## 2. What You Need

### 2.1 Hardware Specifications & Inference Latency

Running 8-Billion parameter Large Language Models locally is compute-intensive. Actual latency depends directly on the processor architecture, available physical RAM, and presence of a dedicated GPU.

#### Hardware Performance Tiers & Observed Latency

| Hardware Tier | Processor (CPU) | System Memory (RAM) | Graphics (GPU) | Observed Latency per Requirement |
| :--- | :--- | :--- | :--- | :--- |
| **Observed Entry-Level Laptop** <br> *(Demonstration Baseline)* | Intel Core i3-7020U <br> (2.30 GHz, 2 cores / 4 threads) | 8 GB DDR4 | Integrated Intel HD 620 <br> *(Pure CPU inference)* | **20 – 30 minutes** <br> *(3 to 5 LLM calls per run)* |
| **Standard Desktop / Workstation** <br> *(Recommended CPU)* | Intel Core i7 (8th Gen+) or <br> AMD Ryzen 7 (8+ cores) | 16 GB – 32 GB DDR4 | Integrated / Non-CUDA <br> *(Pure CPU inference)* | **5 – 10 minutes** <br> *(3 to 5 LLM calls per run)* |
| **GPU Workstation** <br> *(Optimal Engineering Setup)* | Intel Core i7/i9 or <br> AMD Ryzen 7/9 | 32 GB – 64 GB DDR4/DDR5 | Dedicated NVIDIA GPU $\ge$ 8 GB VRAM <br> *(RTX 3060, 4070, A4000+ with CUDA)* | **5 – 15 seconds** <br> *(Full pipeline completion)* |

> [!IMPORTANT]
> **Why pure CPU inference takes 20–30 minutes on a dual-core laptop:**
> A single formalization run does not make just one LLM call. The multi-stage verification architecture executes multiple sequential LLM chat completions:
> 1. **Analyst Stage**: 1 LLM call to extract requirement scope, patterns, and timing constraints.
> 2. **Reasoning Stage (Iteration 1)**: 1 LLM call to generate atomic propositions, predicate definitions, and candidate logic formula.
> 3. **Critic Stage (Iteration 1)**: 1 LLM call for independent verification audit against source text.
> 4. **Revision Stage (Iteration 2, if needed)**: 1 LLM call to revise the candidate formula addressing critic and validator findings.
> 5. **Critic Stage (Iteration 2, if revised)**: 1 LLM call to re-audit the revised candidate.
>
> With the default setting of `max_revisions = 2`, an unverified candidate that requires revision makes **up to 5 full LLM chat completions** (1 Analyst + 2 calls per iteration $\times$ 2 iterations). If the candidate passes verification on the first attempt without revision, it makes **3 full LLM calls** (1 Analyst + 1 Reasoning + 1 Critic).
>
> On a dual-core processor such as the Intel Core i3-7020U (2 cores / 4 threads at 2.3 GHz), each 8B forward generation pass requires approximately 4 to 6 minutes of continuous CPU computation. Therefore, a complete 5-call run accumulates to **20 to 30 minutes total wall-clock time**.

#### System Memory (RAM) Pressure on 8 GB Systems
An 8-Billion parameter model (`llama3:latest`, 4-bit quantized) requires approximately 4.7 GB to 5.0 GB of RAM for model weights and KV context cache. On an 8 GB workstation:
- Windows OS and core background processes consume ~2.5 GB to 3.0 GB of RAM.
- Ollama model weights require ~4.8 GB of RAM.
- Python runtime and web server consume ~200 MB to 400 MB.
- **Total requirement**: ~7.5 GB to 8.2 GB of physical RAM.

This places an 8 GB workstation right at the physical boundary. If external applications (such as web browsers with multiple tabs, IDEs, or office software) remain open, Windows is forced to page inactive memory to the disk swapfile (`pagefile.sys`), causing severe I/O thrashing and compounding inference latency.

#### Conservative CPU Operating Guidelines
To achieve reliable operation without unnecessary delay on entry-level or dual-core workstations:
1. **Reduce Maximum Revisions to 1**:
   In the web UI formalization view or configuration, set **Max Revisions** to `1` (or use default with understanding). This caps the run at a maximum of 3 LLM calls (1 Analyst + 1 Reasoning + 1 Critic, plus 1 revision pass only if needed), cutting total run time by approximately 40% to 50% (~12 to 15 minutes instead of 25 to 30 minutes).
   - *Safety Trade-off*: The model is given only 1 revision attempt to satisfy the critic. If the candidate still has defects after 1 revision, the pipeline concludes safely with status `REVISION LIMIT REACHED`. **No validation or critic safeguards are bypassed**—deterministic structural and symbol validators still enforce strict safety, and all candidate formulas and findings are preserved for engineer review.
2. **Close Unnecessary Applications**:
   Close RAM-heavy applications (especially Google Chrome, Microsoft Edge tabs, and IDEs) before initiating live inference to guarantee dedicated physical RAM for Ollama.
3. **Avoid Batch Runs on Dual-Core CPUs**:
   Do not run section-level batch formalizations (e.g. 5+ requirements) on dual-core CPU machines during live demonstrations, as a batch will take 1.5 to 2.5 hours. Instead, demonstrate single-requirement execution or inspect previously computed runs in the **Formalization History** ledger (`/history`).
4. **Use Pre-computed History for Reviews**:
   The Formalization History ledger (`data/history_store.json`) persists full mathematical formulas, proposition definitions, and verification audits for previously analyzed requirements (such as SRS017, SRS178, SRS194, SRS234, SRS014). ADE engineers can inspect, audit, and evaluate these results instantaneously without triggering any model re-computation.

### 2.2 Software Requirements
All required software can be downloaded once while connected to the internet and transferred via approved media to the offline workstation:
1. **Python**: Version **3.10, 3.11, or 3.12** (64-bit) for Windows.
2. **Ollama for Windows**: Local LLM server executable (`OllamaSetup.exe`).
3. **Web Browser**: Google Chrome, Microsoft Edge, or Mozilla Firefox.

### 2.3 Required Language Models
The application is pre-configured to use:
- **`llama3:latest`** (Meta Llama 3 8-Billion parameter model, approximately 4.7 GB).
- *Optional alternatives*: `deepseek-r1:8b`, `mistral:7b`, or `phi3:mini`.

### 2.4 Required Project Assets
The deployment ZIP package must contain:
- `app/` (all core backend, pipeline, and UI code)
- `data/` (contains `symbol_registry.json`, `model_config.json`, `history_store.json`, `result_cache.json`, and source documents)
- `docs/` (documentation and manuals)
- `SRS-Knowledge/` (frozen engineering knowledge vault with pattern definitions)
- `srs_canonical.db` (canonical SQLite database with extracted requirements)
- `run_ui.py` (application startup script)
- `requirements.txt` (list of Python libraries)

---

## 3. Preparing the Computer While Internet Access Is Available

Follow these steps on a machine with internet access before moving to the isolated network.

### Step 1: Install Python
1. Download **Python 3.11** (Windows 64-bit installer) from [python.org](https://www.python.org/downloads/).
2. Run the installer.
3. **CRITICAL**: On the very first installation screen, check the box that says:
   $$\mathbf{[\checkmark]\ Add\ python.exe\ to\ PATH}$$
4. Click **Install Now** and wait for completion.

### Step 2: Install Ollama
1. Download **Ollama for Windows** from [ollama.com/download/windows](https://ollama.com/download/windows).
2. Run `OllamaSetup.exe` and complete the installation wizard.
3. Ollama will start automatically and appear as an icon in your Windows taskbar system tray.

### Step 3: Download the Required LLM Model
1. Open **Windows PowerShell** or **Command Prompt** (press `Win + R`, type `powershell`, and press Enter).
2. Run the following command to download the default model:
   ```powershell
   ollama pull llama3:latest
   ```
3. Ollama will download the model weights (approx. 4.7 GB).
4. Verify that the model is ready by listing installed models:
   ```powershell
   ollama list
   ```
   *Expected output:*
   ```text
   NAME             ID           SIZE      MODIFIED
   llama3:latest    365c0b3c0e10 4.7 GB    About a minute ago
   ```

### Step 4: Download Python Dependencies (For Offline Transfer)
If the target workstation is already disconnected from the internet, you can create an offline package of all required Python libraries:
1. Open PowerShell and navigate to the project directory:
   ```powershell
   cd C:\Path\To\SRS-Formalization-Agent
   ```
2. Download all library installation packages (`.whl` files) into a local folder:
   ```powershell
   pip download -r requirements.txt -d .\wheelhouse
   ```
3. This creates a folder named `wheelhouse/` containing the exact offline installation packages for `Flask`, `python-docx`, `pypdf`, `ollama`, and their sub-dependencies.

### Step 5: Offline User Interface Assets (Pre-Bundled)
The web user interface is 100% self-hosted and does **not** rely on external internet CDNs or browser pre-caching:
- All required Bootstrap 5.3.0 CSS and JavaScript libraries are pre-packaged under `app/ui/static/vendor/bootstrap/`.
- All required Bootstrap Icons 1.10.0 stylesheets and Web Open Font Format files (`.woff2`, `.woff`) are pre-packaged under `app/ui/static/vendor/bootstrap-icons/`.
- All assets are distributed under the official open-source MIT License with license files included in the respective directories.
- No network requests are made to `cdn.jsdelivr.net` or any external server when loading or navigating pages.

---

## 4. Transferring the Application

### 4.1 Creating the Transfer Package
Create a standard ZIP archive of the `SRS-Formalization-Agent` folder. Ensure the following files and folders are included:

```text
SRS-Formalization-Agent/
├── app/                        [Included - Full application source]
│   ├── ui/
│   │   ├── static/
│   │   │   ├── css/            [Custom application styles]
│   │   │   └── vendor/         [Bundled offline vendor assets]
│   │   │       ├── bootstrap/          [Bootstrap 5.3.0 CSS, JS & LICENSE]
│   │   │       └── bootstrap-icons/    [Bootstrap Icons 1.10.0 CSS, fonts & LICENSE]
│   │   └── templates/          [HTML templates with local static references]
│   └── ...
├── data/                       [Included - Registry, configs, PDF, caches]
│   ├── history_store.json
│   ├── model_config.json
│   ├── nasax38 SRS.pdf
│   ├── result_cache.json
│   └── symbol_registry.json
├── docs/                       [Included - Manuals & specifications]
├── SRS-Knowledge/              [Included - Knowledge vault & pattern registry]
├── tests/                      [Included - Verification test suites]
├── requirements.txt            [Included - Dependency manifest]
├── run_ui.py                   [Included - Main startup script]
├── srs_canonical.db            [Included - Canonical SQLite requirement database]
└── wheelhouse/                 [Included if created - Offline Python wheels]
```

> **What to exclude (saves space)**:
> - You do **NOT** need to include `.git/` (version control history).
> - You do **NOT** need to include `.venv/` (virtual environment; create a fresh one on the target machine).
> - You do **NOT** need to include `__pycache__/` folders.

### 4.2 Extracting the ZIP on the Target Computer
1. Copy the ZIP file to the offline target computer using authorized secure media.
2. Extract the ZIP into a clean, standard local directory with write permissions, such as:
   `C:\DRDO\SRS-Formalization-Agent`
3. Verify that the directory contains `run_ui.py`, `srs_canonical.db`, `SRS-Knowledge`, and the `data` folder.

---

## 5. Running the Application Offline

Follow these simple steps on the offline computer:

### Step 1: Open Windows PowerShell
1. Press the `Windows Key`.
2. Type `PowerShell`.
3. Click **Windows PowerShell**.

### Step 2: Navigate to the Extracted Folder
Type the `cd` command followed by the path to the extracted folder:
```powershell
cd C:\DRDO\SRS-Formalization-Agent
```

### Step 3: (Recommended) Create and Activate a Python Virtual Environment
Creating an isolated environment keeps the application stable:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```
*(If PowerShell shows an execution policy warning, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` and then run the Activate command again).*

### Step 4: Install Python Dependencies
- **If online or on an internal intranet index**:
  ```powershell
  pip install -r requirements.txt
  ```
- **If completely offline using the transferred `wheelhouse` folder**:
  ```powershell
  pip install --no-index --find-links=.\wheelhouse -r requirements.txt
  ```

### Step 5: Verify that Ollama Is Running Offline
In PowerShell, check that Ollama is active and that your model is ready:
```powershell
ollama list
```
You should see `llama3:latest` listed. If Ollama is not running, launch it from the Windows Start menu or run:
```powershell
ollama serve
```

### Step 6: Start the SRS Formalization Agent
Run the application startup script:
```powershell
python run_ui.py
```

*Expected startup output:*
```text
Initializing SQLite database...
Database initialized at: srs_canonical.db
Starting Flask web server on http://127.0.0.1:5000/
Press Ctrl+C to stop.
 * Serving Flask app 'app.ui.app'
 * Debug mode: on
 * Running on http://127.0.0.1:5000
```

### Step 7: Open the Application in Your Browser
Open Chrome, Edge, or Firefox and navigate to:
$$\mathbf{http://127.0.0.1:5000/}$$

### Step 8: Stopping the Application
When finished, click into the PowerShell window and press `Ctrl + C` once. The server will shut down safely.

---

## 6. First-Use Instructions (Non-Programmer Guide)

### 6.1 Checking Model Settings
1. Click **Model settings** in the top navigation bar.
2. The page queries your local Ollama installation and displays all detected models.
3. Verify that:
   - **Analyst model**: `llama3:latest`
   - **Reasoning model**: `llama3:latest`
   - **Critic model**: `llama3:latest`
4. Click **Save Model Selections**.

### 6.2 Formalizing an Individual Requirement
1. Click **Dashboard** in the top navigation bar.
2. Under **NASA X-38 Software Requirements Specification**, select **Browse Document** or click on a section (e.g., **3.2.1 System Initialization**).
3. The page displays the requirements extracted from that section.
4. Next to any requirement (e.g., `[SRS178]`), click **Run Formalization**.
5. The application will execute the end-to-end 6-stage pipeline:
   - **Stage 1**: Displays source requirement text, section provenance, and prerequisite dependencies.
   - **Stage 2**: Defines atomic propositions with explicit notation (e.g. `P_RESET := power-on reset occurs`) and provenance tags.
   - **Stage 3**: Declares state predicates, arguments (e.g. `install_task(task, rate_group)`), entities, and condition types.
   - **Stage 4**: Displays the candidate formal mathematical logic formula referencing declared symbols (no embedded definitions).
   - **Stage 5**: Explains the step-by-step formula construction and composition rules.
   - **Stage 6**: Reports deterministic structural validation, canonical symbol validation, constraint provenance table, and unstated parameters.
6. The completed **Full View** will display the results with clear status badges and findings.

### 6.3 Batch Formalization Workflow (Section Clusters)
When multiple related requirements belong to the same functional area:
1. In the Document Browser, open a section containing multiple requirements (e.g., Section 3.2.1 or 3.2.2.1).
2. Click **Batch Formalize Section**.
3. The system executes the **Set-Level Analyst** first:
   - Clusters requirements within section boundaries.
   - Extracts shared domain entities, hardware devices, and signal buses.
   - Identifies cross-requirement dependencies (e.g. `[SRS016]` -> `[SRS017]`).
   - Generates a batch context summary injected into each requirement's reasoning prompt.
4. Formalizes each requirement sequentially, displaying progress and status badges.
5. Persists the complete batch run into `data/history_store.json` with aggregate status counts.

### 6.4 Managing the Symbol Registry
1. Click **Symbol Registry** in the top navigation bar (`/symbols`).
2. The page lists all registered symbols across 7 categories:
   - `PROPOSITION`, `PREDICATE`, `ENTITY`, `VARIABLE`, `CONSTANT`, `TEMPORAL_OPERATOR`, `LOGICAL_CONNECTIVE`.
3. Filter symbols by category, scope (e.g. `[SRS017]` or `global`), or search keywords.
4. Model-generated symbols are initially tagged with a **Proposal** badge.
5. Domain engineers can inspect symbol definitions, edit notations, and click **Approve Symbol** to mark them as verified domain invariants.

### 6.5 Understanding Pipeline Statuses & Badges
The system never marks a candidate as valid merely because the pipeline finished executing. Statuses are distinguished across the pipeline, history, and UI:

| Status Badge | CSS / Icon | Engineering Meaning |
| :--- | :--- | :--- |
| **`PASS`** | Green (`success`) <br> `bi-check-circle-fill` | **Accepted Candidate**: The formula passed independent Critic review, satisfied all deterministic structural checks, complied with canonical symbol registry definitions, and has **zero** open clarification items. |
| **`PASS (NEEDS CLARIFICATION)`** | Yellow (`warning`) <br> `bi-question-circle-fill` | **Clarification Required**: The mathematical formula is syntactically and symbolically valid, but unstated parameters, missing timing thresholds, or engineer assumptions require human review before final verification. |
| **`INVALID FORMULA`** | Red (`danger`) <br> `bi-slash-circle-fill` | **Candidate Rejected by Validation**: The formula failed deterministic structural validation (e.g., unbalanced parentheses, operator missing operand) or symbol validation (e.g., undeclared predicate symbol, unjustified `U` operator, or embedded `:=` definition prose). Cannot be accepted regardless of Critic assessment. |
| **`REVISION LIMIT REACHED`** | Yellow (`warning`) <br> `bi-arrow-repeat` | **Revision Limit Reached**: The automated reasoning-critic loop exhausted its configured limit (e.g., 2 passes) without reaching complete convergence. All candidate iterations and critic findings are preserved for engineer inspection. |
| **`BLOCKED`** | Red (`danger`) <br> `bi-x-octagon-fill` | **Critic Blocked**: The Critic identified an unresolvable contradiction or explicit requirement impossibility preventing further automated revision passes. |
| **`FAILED`** | Red (`danger`) <br> `bi-x-circle-fill` | **Execution Failure**: The pipeline encountered a system-level runtime error (e.g., Ollama daemon unreachable, SQLite read error, or invalid JSON payload). The specific failing stage is flagged in the error banner. |

### 6.6 Deterministic Validation vs. Semantic Correctness
It is critical for ADE engineers and reviewers to understand the division of responsibility:
- **Deterministic Validation (Algorithmic)**:
  - Validates that delimiters (`()`, `[]`, `{}`) are strictly balanced.
  - Validates that temporal operators (`G`, `F`, `X`) have explicit operands.
  - Validates that logical connectives (`->`, `&&`, `||`) have operands on both sides.
  - Validates that every referenced proposition and predicate argument is declared in the intermediate representation or Symbol Registry.
  - Validates that definition syntax (`:=`) is not embedded into the formula.
  - Validates that temporal Until (`U`) is justified by source requirement text keywords or structural patterns.
  - *Limitation*: Passing deterministic validation verifies **grammatical and lexical soundness**, NOT that the formula captures the true avionics engineering intent.
- **Semantic Correctness (Domain Review)**:
  - Audited by the independent Critic model against the source text and retrieved pattern knowledge.
  - Verified and confirmed by human flight-software engineers through the Full View UI and Clarification workflow.

### 6.7 Answering Clarification Questions
If a requirement has ambiguous timing bounds or unstated engineering parameters:
1. The Full View page displays a **Clarifications** tab.
2. Each question presents stakeholder options (e.g., selecting between 10ms or 20ms, or entering custom engineering notes).
3. Select your answer and click **Submit Answer & Re-run**.
4. The system incorporates your answer and automatically re-formalizes the requirement.

### 6.8 Viewing Formalization History (Without Re-running Models)
You do not need to re-run expensive local models to inspect results that were generated previously:
1. Click **Formalization History** in the top navigation bar.
2. The page displays an overview ledger with:
   - Total runs and evaluations.
   - Status breakdown (`PASS`, `PASS (NEEDS CLARIFICATION)`, `INVALID FORMULA`, `REVISION LIMIT REACHED`, `FAILED`).
   - Reverse-chronological ledger of all single and batch runs.
   - Search box (filter by requirement ID, SRS tag, or text snippet).
3. Click **Inspect Run** to view full mathematical formulas, interpretations, and validation findings instantly.

---

## 7. Troubleshooting Common Issues

### Problem 1: `'python' is not recognized as an internal or external command`
- **Cause**: Python was installed without checking the "Add python.exe to PATH" box.
- **Solution**:
  1. Re-run the Python Windows installer.
  2. Choose **Modify**.
  3. Ensure **Add Python to environment variables** is checked and complete the installation.
  4. Close and re-open PowerShell.

### Problem 2: `Ollama is unavailable or returned invalid installed-model data: connection refused`
- **Cause**: The Ollama background service is not running.
- **Solution**:
  1. Open the Windows Start menu and click **Ollama** to start it.
  2. Or open a new PowerShell window and run: `ollama serve`.
  3. Verify in browser at `http://localhost:11434/` (should display *"Ollama is running"*).

### Problem 3: `Configured Ollama model(s) are not installed: llama3:latest`
- **Cause**: The application is configured to look for `llama3:latest`, but the model has not been pulled.
- **Solution**:
  1. Open PowerShell and run: `ollama pull llama3:latest`.
  2. If using a different model (e.g. `mistral`), open `http://127.0.0.1:5000/settings/models` in your browser and select the model from the dropdown.

### Problem 4: `Address already in use` or Port 5000 Conflict
- **Cause**: Another application (or an existing instance of the agent) is already using port 5000.
- **Solution**:
  1. Close any existing Python command-line windows.
  2. To start the agent on an alternate port (e.g., 5050), run:
     ```powershell
     python -c "from app.ui.app import app; app.run(port=5050)"
     ```
  3. Access the application at `http://127.0.0.1:5050/`.

### Problem 5: Web Page Styling or Icons Fail to Render
- **Cause**: Static assets under `app/ui/static/vendor/` are missing, corrupted, or have restricted file permissions.
- **Solution**:
  1. The application bundles all CSS, JS, and font files locally. Verify that the following files exist on disk:
     - `app/ui/static/vendor/bootstrap/css/bootstrap.min.css`
     - `app/ui/static/vendor/bootstrap/js/bootstrap.bundle.min.js`
     - `app/ui/static/vendor/bootstrap-icons/bootstrap-icons.css`
     - `app/ui/static/vendor/bootstrap-icons/fonts/bootstrap-icons.woff2`
  2. In your browser, open Developer Tools (`F12`), switch to the **Console** or **Network** tab, and reload the page (`Ctrl + F5`). Ensure static assets return HTTP `200` status from `http://127.0.0.1:5000/static/vendor/...`.
  3. No internet connection or CDN access is required.

### Problem 6: Model Takes 20–30 Minutes per Requirement
- **Cause**: Pure CPU execution on an entry-level processor (e.g., dual-core Intel Core i3-7020U, 2 cores/4 threads) combined with multi-stage LLM evaluation (up to 5 sequential LLM calls per run) and memory pressure on 8 GB RAM.
- **Solution**:
  1. **Reduce Max Revisions**: On the formalization page or in configuration, set `max_revisions = 1`. This reduces the maximum number of LLM calls from 5 to 3, cutting execution time to ~12–15 minutes on dual-core hardware.
  2. **Audit Without Re-running**: For demonstration and review purposes, use the **Formalization History** page (`/history`) to inspect pre-computed results immediately without waiting for inference.
  3. **Free Up Physical RAM**: Close memory-heavy background applications (Google Chrome, Edge, IDEs) before starting inference to prevent Windows from paging Ollama memory to disk.
  4. **Deploy on Recommended Hardware**: On a multi-core workstation (i7/Ryzen 7 with 16–32 GB RAM), CPU inference takes ~5–10 minutes. On a workstation with a dedicated NVIDIA GPU ($\ge$ 8 GB VRAM), inference completes in 5–15 seconds.

---

## 8. Offline Security and Data Handling

### 8.1 Data Storage Locations
All application data is strictly self-contained within the project root folder:
- **`srs_canonical.db`**: Stores requirements, section hierarchies, and target groups.
- **`data/history_store.json`**: Stores the persistent ledger of formalization results.
- **`data/result_cache.json`**: Stores cached individual evaluations for Full View.
- **`data/model_config.json`**: Stores model stage assignments.
- **`data/symbol_registry.json`**: Stores mathematical and domain symbol definitions.
- **`SRS-Knowledge/`**: Read-only Markdown notes for pattern templates and domain concepts.

### 8.2 Verification of Zero External Network Traffic
You can independently verify that the application makes no external connections:
1. Open Windows PowerShell and run `netstat -ano | findstr 5000`. You will observe only internal loopback communication (`127.0.0.1:5000`).
2. Run `netstat -ano | findstr 11434`. You will observe only internal loopback communication between Python and Ollama (`127.0.0.1:11434`).
3. There are zero outbound sockets opened to any external IP address.
4. Inspection of `app/ui/templates/base.html` confirms all stylesheet and script references use local static routing (`url_for('static', filename='vendor/...')`) with zero external CDN references.

### 8.3 Safe Backup Procedure
To back up all generated formalizations, user clarifications, and settings:
Simply copy the **`data/`** directory and **`srs_canonical.db`** file to a secure backup directory or external storage media.

---

## 9. Known Limitations and Future Deployment Enhancements

1. **Local Static Asset Bundling (Resolved in Current Release)**:
   - All Bootstrap 5.3.0 and Bootstrap Icons 1.10.0 stylesheets, JavaScript bundles, and font binaries (`woff2`, `woff`) are now bundled directly under `app/ui/static/vendor/` with official MIT licenses.
   - The user interface operates 100% offline out-of-the-box on fresh, air-gapped systems without requiring external network connectivity or pre-warmed browser caches.
2. **Synchronous Web Inference**:
   - Running formalization blocks the Flask web thread until the model finishes responding.
   - When running on dual-core CPU hardware, the browser tab shows a loading spinner during the run. The page should not be refreshed or interrupted during this period.
3. **Linux / Unix Verification**:
   - The application has been developed and verified on Windows 10/11. While Python code is largely cross-platform, deployment on ADE Linux workstations has not yet been formally verified in this milestone.

---

## 10. Final Deployment Checklist

Before handing the workstation over to end-users at ADE, verify each item:

- [ ] **Python Installed**: Python 3.10–3.12 installed with `Add python.exe to PATH` checked.
- [ ] **Ollama Installed**: Ollama is installed and running in the system tray.
- [ ] **Model Downloaded**: `ollama list` confirms `llama3:latest` is present.
- [ ] **Dependencies Installed**: `pip list` confirms `Flask`, `python-docx`, `pypdf`, and `ollama` are installed.
- [ ] **Database Present**: `srs_canonical.db` exists in the project root directory.
- [ ] **Knowledge Vault Intact**: `SRS-Knowledge/Index/Pattern-Registry.json` is present.
- [ ] **Symbols Registered**: `data/symbol_registry.json` is present.
- [ ] **Offline UI Assets Present**: `app/ui/static/vendor/` contains Bootstrap and Bootstrap Icons stylesheets, scripts, and fonts. Web UI renders completely styled without internet access.
- [ ] **Air-Gap Verification**: Disconnect the network cable / Wi-Fi.
- [ ] **Server Starts**: `python run_ui.py` displays `Running on http://127.0.0.1:5000`.
- [ ] **Web UI Loads**: Navigating to `http://127.0.0.1:5000/` opens the SRS Formalization Dashboard.
- [ ] **History Available**: Navigating to `http://127.0.0.1:5000/history` displays the 5 recovered requirements without re-running models.
