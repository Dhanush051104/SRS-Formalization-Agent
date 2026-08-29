# Database Documentation: SQLite Canonical Store

The **SRS Formalization Agent** uses a local SQLite database (`srs_canonical.db`) as its canonical source of truth. The database stores the structured document content, extracted requirements, section tree, and user-defined target groups.

---

## 1. Database Philosophy

The SQLite store is designed to be **lossless**. Rather than discarding parts of the document that are not explicitly classified as requirements, the database retains every parsed block of text in its original order of appearance. This preservation allows the system to:
1. Reconstruct document contents exactly as they appear in the original source file.
2. Maintain full audit traceability from any target analysis group back to the specific raw PDF elements and page numbers.

---

## 2. Table Schemas & Relationships

```
+-----------------+
|    documents    |
+-----------------+
        |
        +-------------------+-------------------+-------------------+
        | 1                 | 1                 | 1                 | 1
        v M                 v M                 v M                 v M
+-----------------+ +-----------------+ +-----------------+ +-----------------+
|      pages      | |    elements     | |    sections     | |  requirements   |
+-----------------+ +-----------------+ +-----------------+ +-----------------+
                                                |                   | 1
                                                |                   v M
                                                |           +-----------------+
                                                |           |  target_group_  |
                                                |           |     members     |
                                                |           +-----------------+
                                                |                   ^ M
                                                | 1                 | 1
                                                |                   |
                                                +------------> target_groups  |
                                                              +-----------------+
```

### 1. `documents`
Stores metadata about ingested documents.
- `id` (INTEGER, Primary Key): Unique document ID.
- `filename` (TEXT): Name of the file (e.g., `nasaX38 SRS.pdf`).
- `filepath` (TEXT): Absolute or relative source file path.
- `uploaded_at` (TEXT): ISO-8601 timestamp of when the file was processed.

### 2. `pages`
Stores page index mappings.
- `id` (INTEGER, Primary Key): Unique page record ID.
- `document_id` (INTEGER, Foreign Key referencing `documents(id)` ON DELETE CASCADE).
- `page_number` (INTEGER): The source document page number.

### 3. `elements`
Contains the raw, lossless text output from the parser.
- `id` (INTEGER, Primary Key)
- `document_id` (INTEGER, Foreign Key referencing `documents(id)` ON DELETE CASCADE)
- `page_number` (INTEGER): Source page where the element is located.
- `element_index` (INTEGER): 0-indexed position maintaining the exact sequence of elements.
- `parser_type` (TEXT): Source block type (e.g., `text`, `table_row`).
- `parser_style` (TEXT): Formatting styling if extracted.
- `classification` (TEXT): Categorization of the element (`regular_content`, `section_heading`, or `requirement`).
- `raw_text` (TEXT): Original uncleaned string.
- `normalized_text` (TEXT): Cleaned or processed representation.

### 4. `sections`
Maintains the structured tree hierarchy of document sections.
- `id` (INTEGER, Primary Key)
- `document_id` (INTEGER, Foreign Key referencing `documents(id)` ON DELETE CASCADE)
- `number` (TEXT): Section number (e.g., `3.2.1`).
- `title` (TEXT): Section header title (e.g., `System Initialization`).
- `page_number` (INTEGER): Page number where the heading begins.
- `parent_number` (TEXT, Nullable): Parent section number (e.g., `3.2`).
- `element_index` (INTEGER): The index in the `elements` table where this heading starts.

### 5. `requirements`
Tracks individual SRS requirements.
- `id` (INTEGER, Primary Key)
- `document_id` (INTEGER, Foreign Key referencing `documents(id)` ON DELETE CASCADE)
- `section_id` (INTEGER, Foreign Key referencing `sections(id)` ON DELETE CASCADE)
- `section_number` (TEXT): Helper field for queries (e.g., `3.2.1`).
- `srs_id` (TEXT): The unique tag parsed from the text (e.g., `[SRS194]`).
- `global_number` (INTEGER): Sequential 1-indexed count across the whole document (e.g., `1` to `195`).
- `source_number` (INTEGER): The section-relative local requirement number (e.g., `1` to `17`).
- `raw_text` (TEXT): Unmodified requirement statement.
- `normalized_text` (TEXT): Cleaned/consolidated requirement sentence.
- `page_number` (INTEGER)
- `element_index` (INTEGER): The starting index in the `elements` table.

### 6. `target_groups`
Stores user-defined target groupings of requirements for reasoning.
- `id` (INTEGER, Primary Key)
- `document_id` (INTEGER, Foreign Key referencing `documents(id)` ON DELETE CASCADE)
- `section_number` (TEXT): The section number where the selection occurred.
- `created_at` (TEXT): Timestamp.
- `status` (TEXT): Current lifecycle status (defaults to `'Ready for Analysis'`).

### 7. `target_group_members`
Association table connecting target groups to canonical requirements.
- `id` (INTEGER, Primary Key)
- `target_group_id` (INTEGER, Foreign Key referencing `target_groups(id)` ON DELETE CASCADE)
- `requirement_id` (INTEGER, Foreign Key referencing `requirements(id)` ON DELETE CASCADE)
- `selection_order` (INTEGER): Maintains the user's explicit selection sequence (1-indexed).
- **Constraints:** `UNIQUE(target_group_id, requirement_id)` ensures a requirement cannot be added to a group multiple times.

---

## 3. How to Inspect the Database

You can inspect `srs_canonical.db` directly without using the Flask application.

### Option A: Using the SQLite Command Line Interface
If you have `sqlite3` installed in your terminal environment, execute:

```powershell
sqlite3 srs_canonical.db
```

Once in the SQLite shell, you can run diagnostic commands:
* `.tables` — Lists all tables.
* `.schema <table_name>` — Displays the table schema.
* `SELECT * FROM target_groups;` — View target groups.
* `SELECT number, title FROM sections WHERE parent_number = '3.2';` — Query subsections.
* `.exit` — Exit the shell.

### Option B: Using a Graphical Interface
For Windows environments without the terminal CLI installed, we recommend using a free GUI database inspector:
1. Download **DB Browser for SQLite (DB4S)** (https://sqlitebrowser.org/).
2. Open DB Browser and click **Open Database**.
3. Select `srs_canonical.db` in your repository root.
4. Browse tables, view schema relationships, and execute custom SQL queries visually.

### Option C: Quick Python Diagnostic Script
You can write a simple Python script to fetch and print details programmatically:

```python
import sqlite3

conn = sqlite3.connect("srs_canonical.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Query requirements in section 3.2.1
cursor.execute("SELECT global_number, srs_id FROM requirements WHERE section_number = '3.2.1';")
for row in cursor.fetchall():
    print(f"R{row['global_number']}: {row['srs_id']}")

conn.close()
```
