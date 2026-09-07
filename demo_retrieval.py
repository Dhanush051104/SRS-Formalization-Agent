import json
import sys
from pathlib import Path

# Ensure UTF-8 output encoding for Windows PowerShell / CMD environments
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure project root is in sys.path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.retrieval import (
    ContextBuilder,
    ContextPackage,
    ObsidianRetriever,
    ObsidianRetrieverError,
    SQLiteRetriever,
    SQLiteRetrieverError,
)


def run_demo() -> None:
    print("==========================================================")
    print("      SRS FORMALIZATION AGENT — RETRIEVAL DEMO           ")
    print("==========================================================")
    print()

    requirement_ids = [5]
    pattern_names = [
        "Timeout / Deadline",
        "Bounded Waiting",
        "Failure Handling",
        "Component Interaction",
        "Cross-Requirement Dependency",
    ]

    try:
        sqlite_retriever = SQLiteRetriever()
        obsidian_retriever = ObsidianRetriever()
        builder = ContextBuilder(
            sqlite_retriever=sqlite_retriever,
            obsidian_retriever=obsidian_retriever,
        )

        package: ContextPackage = builder.build(
            requirement_ids=requirement_ids,
            pattern_names=pattern_names,
        )

        print("----------------------------------------------------------")
        print("2. TARGET REQUIREMENT")
        print("----------------------------------------------------------")
        for req in package.requirements:
            print(f"  • Requirement ID:        {req.requirement_id}")
            print(f"  • Global Number:         R{req.global_number}")
            print(f"  • SRS ID:                {req.srs_id}")
            print(f"  • Section Number:        {req.section_number}")
            print(f"  • Section Title:         {req.section_title}")
            print(f"  • Exact Raw Text:\n    \"{req.raw_text}\"")
            print()

        print("----------------------------------------------------------")
        print("3. DEMO PATTERN INPUT (PATTERNS PROVIDED TO RETRIEVAL LAYER)")
        print("----------------------------------------------------------")
        for idx, name in enumerate(package.identified_patterns, 1):
            print(f"  {idx}. {name}")
        print()

        print("----------------------------------------------------------")
        print("4. RETRIEVED OBSIDIAN KNOWLEDGE")
        print("----------------------------------------------------------")
        obs_res = package.obsidian_knowledge
        for item in obs_res.pattern_items:
            print(f"  [Pattern] {item.requested_pattern}")
            print(f"    - Pattern ID:          {item.pattern_id}")
            print(f"    - Note Path:           {item.pattern_file_path}")

            form_paths = [fn.file_path for fn in item.formalization_notes]
            print(f"    - Formalization Notes: {', '.join(form_paths) if form_paths else 'None'}")

            concept_paths = [cn.file_path for cn in item.concept_notes]
            print(f"    - Concept Notes:       {', '.join(concept_paths) if concept_paths else 'None'}")
            print()

        print("----------------------------------------------------------")
        print("5. CONTEXTPACKAGE SUMMARY")
        print("----------------------------------------------------------")
        print(f"  • Number of Requirements: {len(package.requirements)}")
        print(f"  • Number of Patterns:     {len(package.identified_patterns)}")
        print(f"  • Loaded Files Count:     {obs_res.loaded_files_count}")
        print(f"  • Read Cache Hits:        {obs_res.read_cache_hits}")
        print()

        print("----------------------------------------------------------")
        print("6. PROVENANCE")
        print("----------------------------------------------------------")
        print(json.dumps(package.provenance, indent=2))
        print()

        print("==========================================================")
        print("✓ CONTEXTPACKAGE SUCCESSFULLY ASSEMBLED")
        print("✓ READY TO BE PROVIDED TO THE FUTURE REASONING MODEL")
        print("==========================================================")

    except SQLiteRetrieverError as e:
        print(f"[ERROR] SQLite Retrieval Error encountered: {e}")
        sys.exit(1)
    except ObsidianRetrieverError as e:
        print(f"[ERROR] Obsidian Retrieval Error encountered: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Unexpected Error encountered: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_demo()
