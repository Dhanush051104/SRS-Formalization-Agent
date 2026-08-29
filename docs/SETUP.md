# Developer Setup Guide

This guide provides step-by-step setup instructions for configuring a local developer environment on Windows (using PowerShell).

---

## 1. Installation and Virtual Environment Setup

First, clone the repository and navigate into the root directory:

```powershell
git clone <repository_url>
cd SRS-Formalization-Agent
```

Create a local Python virtual environment to isolate dependencies:

```powershell
python -m venv .venv
```

Activate the virtual environment in Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

> [!NOTE]
> If you encounter an execution policy error (e.g., script execution is disabled on this system), you can temporarily enable it for your current PowerShell session using:
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process`

Upgrade `pip` and install the project dependencies:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

## 2. Running the Test Suites

To avoid `ModuleNotFoundError` errors, **always run python scripts and tests from the project root directory** using the `python -m` syntax rather than running files directly.

For example, do NOT run:
`python tests/test_parser.py` (Raises `ModuleNotFoundError: No module named 'app'`)

Instead, run:
`python -m tests.test_parser`

### Test Commands

#### 1. Ingestion Parser Diagnostics
Runs the raw document extraction parser and prints out diagnostic details of the Section 3 hierarchy:
```powershell
python -m tests.test_parser
```
*Expected Output:* Prints a list of parsed sections and subsection requirements for Section 3, ending with a detailed dump of Section 3.2.1 and exiting with code `0`.

#### 2. Milestone 1 Core Validation Tests
Validates the database schemas, lossless element count (5,379), requirement counts (195), parent-child section relationships, and sequential requirement indexing:
```powershell
python -m tests.test_milestone1
```
*Expected Output:*
```text
Ran 15 tests in ~9.5s
OK
```

#### 3. Section Isolation Tests
Validates that selecting a section in the document browser correctly isolates that section's boundary and does not leak elements from surrounding sections:
```powershell
python -m unittest tests/test_section_isolation.py
```
*Expected Output:*
```text
Ran 4 tests in ~9.5s
OK
```

#### 4. Target Group Tests
Validates validations, selection ordering, database UNIQUE constraints, and target group CRUD operations:
```powershell
python -m unittest tests/test_target_groups.py
```
*Expected Output:*
```text
Ran 13 tests in ~10s
OK
```

---

## 3. Starting the Flask Web UI

To start the local Flask server and initialize/verify the database schemas:

```powershell
python run_ui.py
```

*Expected Output:*
```text
Initializing SQLite database...
Database initialized at: srs_canonical.db
Starting Flask web server on http://127.0.0.1:5000/
Press Ctrl+C to stop.
 * Serving Flask app 'app.ui.app'
 * Debug mode: on
 * Running on http://127.0.0.1:5000
```

Open your browser and navigate to `http://127.0.0.1:5000/` to use the application.

---

## 4. Troubleshooting Common Errors

### Error: `ModuleNotFoundError: No module named 'app'`
* **Cause:** Running python scripts from inside the subfolders or invoking them directly (`python tests/test_parser.py`).
* **Fix:** Always execute commands from the project root directory and use the `-m` flag (e.g., `python -m tests.test_parser`).

### Error: `PermissionError: [WinError 32] The process cannot access the file...`
* **Cause:** A database connection was opened during tests/debugging but not closed, locking the SQLite database file (`test_*.db` or `srs_canonical.db`).
* **Fix:** Close any active Flask servers or python diagnostic shells, delete the corresponding `.db` files, and re-run your command.
