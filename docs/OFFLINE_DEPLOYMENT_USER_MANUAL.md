# Offline Deployment & User Setup Manual
## SRS Formalization Agent
**DRDO – Aeronautical Development Establishment (ADE)**

---

## 1. Introduction

### 1.1 What the SRS Formalization Agent Does
The **Software Requirements Specification (SRS) Formalization Agent** is an engineering AI assistant developed at ADE. It automates the rigorous translation of natural-language defense software requirements (such as flight-critical avionics specifications) into verifiable mathematical representations (such as Linear Temporal Logic — LTL, state predicates, and timing bounds).

The system works through an automated multi-stage pipeline:
1. **Analyst Stage**: Scans the requirement text and matches it to engineering patterns (e.g., *Timeout / Deadline*, *Failure Handling*, *State Transition*).
2. **Context Retrieval**: Deterministically fetches domain concepts, formal grammar templates, and canonical mathematical symbols from a local knowledge vault.
3. **Reasoning Stage**: Uses a local Large Language Model (LLM) to generate candidate mathematical logic and natural-language interpretations.
4. **Critic & Verification Stage**: An independent verification model audits the candidate formula against source constraints, timing bounds, and engineering assumptions.
5. **Deterministic Structural & Symbol Validation**: Algorithmic Python checkers verify that logical operators are syntactically complete and that all symbols conform to the canonical symbol registry.
6. **Revision Loop**: Automatically revises flawed candidate formulas up to a user-configured limit.
7. **Clarification Manager**: Detects unstated engineering bounds and presents structured questions to human engineers.
8. **Results & History Ledger**: Persists all formalization results and execution runs for auditability without requiring expensive re-computation.

### 1.2 Purpose of this Manual
This manual provides complete, step-by-step instructions for installing, configuring, and operating the SRS Formalization Agent **entirely offline** within an air-gapped, high-security environment at ADE.

It is specifically written so that any officer, scientist, or engineer—even without a computer science background or prior programming experience—can set up and use the tool without external assistance.

### 1.3 Verified Offline Status
- **Core Backend & Inference**: **100% Offline-Capable**. The application runs completely locally using SQLite for data storage, local Markdown files for engineering knowledge, and an on-premise Ollama instance for local LLM inference. It requires **no internet access, no cloud APIs (no OpenAI, no Gemini, no Anthropic), and no external servers**.
- **Browser User Interface (Styling Note)**: The web interface uses standard HTML templates. The current template links to Bootstrap CSS and icons via a content delivery network (CDN). In Section 3 and Section 7, this manual explains how to ensure the user interface displays properly offline.

---

## 2. What You Need

### 2.1 Hardware Specifications
Running Large Language Models locally requires reasonable computing capacity:

| Component | Minimum Specification | Recommended Specification (Optimal) |
| :--- | :--- | :--- |
| **Operating System** | Windows 10 (64-bit) or Windows 11 | Windows 10 / 11 (64-bit) |
| **Processor (CPU)** | Intel Core i7 (8th Gen+) or AMD Ryzen 7 | Intel Core i7/i9 (12th Gen+) or AMD Ryzen 7/9 |
| **System Memory (RAM)** | 16 GB DDR4/DDR5 | 32 GB or 64 GB DDR4/DDR5 |
| **Graphics Card (GPU)** | Integrated CPU graphics (runs on CPU) | Dedicated NVIDIA GPU with $\ge$ 8 GB VRAM (RTX 3060, 4070, A4000+) |
| **Available Disk Space** | 15 GB free space (SSD strongly recommended) | 30 GB free space on high-speed NVMe SSD |

> **Note on Speed**: When running on CPU alone (without a dedicated NVIDIA GPU), each formalization step takes approximately 2 to 4 minutes per requirement because the CPU must process billions of mathematical calculations. With a dedicated NVIDIA GPU, inference completes in 5 to 15 seconds.

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

### Step 5: Pre-Cache User Interface Styling (One-Time Browser Cache)
Because the application interface uses standard Bootstrap styles via CDN:
1. While internet is available, start the application once by running:
   ```powershell
   python run_ui.py
   ```
2. Open your browser to `http://127.0.0.1:5000/`.
3. Browse to the **Dashboard**, **Formalization History**, and **Model settings** pages.
4. Your browser will download and store the Bootstrap CSS, icons, and JavaScript files in its local cache.
5. Stop the application in PowerShell by pressing `Ctrl + C`.

---

## 4. Transferring the Application

### 4.1 Creating the Transfer Package
Create a standard ZIP archive of the `SRS-Formalization-Agent` folder. Ensure the following files and folders are included:

```text
SRS-Formalization-Agent/
├── app/                        [Included - Full application source]
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
5. The application will execute the end-to-end pipeline:
   - Identifies engineering patterns.
   - Retrieves Obsidian vault knowledge and mathematical symbols.
   - Synthesizes formal temporal logic.
   - Audits formula syntax and symbol boundaries.
   - Performs Critic verification.
6. The completed **Full View** will display the results with green/yellow status badges:
   - **Formalization**: The mathematical logic formula (e.g., `G(trigger -> F[0, 10ms] response)`).
   - **Deterministic Validation**: Reports structural balance and symbol compliance.
   - **Interpretation**: Plain-English explanation of the logic.
   - **Critic Verdict**: PASS, NEEDS_REVISION, or BLOCKED.

### 6.3 Answering Clarification Questions
If a requirement has ambiguous timing bounds or unstated engineering parameters:
1. The Full View page displays a **Clarifications** tab.
2. Each question presents stakeholder options (e.g., selecting between 10ms or 20ms, or entering custom engineering notes).
3. Select your answer and click **Submit Answer & Re-run**.
4. The system incorporates your answer and automatically re-formalizes the requirement.

### 6.4 Viewing Formalization History (Without Re-running Models)
You do not need to re-run expensive local models to inspect results that were generated previously:
1. Click **Formalization History** in the top navigation bar.
2. The page displays an overview ledger with:
   - Total runs and evaluations.
   - Status breakdown (PASS, NEEDS CLARIFICATION, INVALID FORMULA).
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

### Problem 5: Web Page Looks Unstyled (Missing Colors, Icons, or Broken Tabs)
- **Cause**: The browser is disconnected from the internet and could not load Bootstrap CSS/JS from the CDN link.
- **Solution**:
  1. If internet access was temporarily available, visit the page once to populate browser cache.
  2. For permanent air-gapped environments, the system continues to function correctly (forms submit and data processes normally), but visual styling relies on the browser's cached stylesheet.

### Problem 6: Model Takes Several Minutes per Requirement
- **Cause**: The computer does not have a dedicated NVIDIA GPU, so Ollama is running inference entirely on the CPU.
- **Solution**:
  1. This is normal behavior for CPU inference with an 8-Billion parameter model (~2 to 4 minutes per evaluation).
  2. To reduce execution time, reduce the **Max Revisions** slider on the formalization page from `2` to `1`.
  3. If available, deploy on a workstation equipped with an NVIDIA GPU (Ollama detects CUDA automatically).

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

### 8.3 Safe Backup Procedure
To back up all generated formalizations, user clarifications, and settings:
Simply copy the **`data/`** directory and **`srs_canonical.db`** file to a secure backup directory or external storage media.

---

## 9. Known Limitations and Future Deployment Enhancements

1. **Local Static Asset Bundling**:
   - The user interface currently references Bootstrap via CDN (`jsdelivr.net`).
   - *Future Work*: Download `bootstrap.min.css`, `bootstrap.bundle.min.js`, and `bootstrap-icons` directly into an `app/ui/static/` directory so that styling is 100% self-hosted on completely fresh machines without warming the browser cache.
2. **Synchronous Web Inference**:
   - Running formalization blocks the Flask web thread until the model finishes responding.
   - When running on CPU, the browser tab shows a loading spinner for 2 to 4 minutes. The page should not be refreshed during this period.
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
- [ ] **Air-Gap Verification**: Disconnect the network cable / Wi-Fi.
- [ ] **Server Starts**: `python run_ui.py` displays `Running on http://127.0.0.1:5000`.
- [ ] **Web UI Loads**: Navigating to `http://127.0.0.1:5000/` opens the SRS Formalization Dashboard.
- [ ] **History Available**: Navigating to `http://127.0.0.1:5000/history` displays the 5 recovered requirements without re-running models.
