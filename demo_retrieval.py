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

from app.analyst import (
    AnalystError,
    AnalystResult,
    AnalystValidationError,
    NonCanonicalPatternError,
    OllamaAnalyst,
)
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
    print("      SRS FORMALIZATION AGENT — ANALYST DEMO             ")
    print("==========================================================")
    print()

    target_requirement_id = 8  # Requirement R8 / [SRS178]

    try:
        # 1. Retrieve canonical requirement context from SQLite
        sqlite_retriever = SQLiteRetriever()
        req_context = sqlite_retriever.get_requirement_by_id(target_requirement_id)

        print("----------------------------------------------------------")
        print("2. TARGET REQUIREMENT")
        print("----------------------------------------------------------")
        print(f"  • Requirement ID:        {req_context.requirement_id}")
        print(f"  • Global Number:         R{req_context.global_number}")
        print(f"  • SRS ID:                {req_context.srs_id}")
        print(f"  • Section Number:        {req_context.section_number}")
        print(f"  • Section Title:         {req_context.section_title or 'N/A'}")
        print(f"  • Exact Raw Text:\n    \"{req_context.raw_text}\"")
        print()

        # 2. Invoke local Llama 3 Analyst Model via Ollama
        print("Running Llama 3 Analyst Model via Ollama...")
        analyst = OllamaAnalyst(model="llama3:latest")
        
        analyst_result: AnalystResult = analyst.analyze(req_context)

        print("----------------------------------------------------------")
        print("3. PATTERNS IDENTIFIED BY LLAMA 3 ANALYST MODEL")
        print("----------------------------------------------------------")
        if not analyst_result.identified_patterns:
            print("  (No canonical patterns identified for this requirement)")
        else:
            for idx, name in enumerate(analyst_result.identified_patterns, 1):
                evidence = analyst_result.evidence.get(name, "No evidence provided")
                print(f"  {idx}. {name}")
                print(f"     Evidence: \"{evidence}\"")

        if analyst_result.missing_information:
            print()
            print("  [Missing Information / Ambiguities Flagged]:")
            for item in analyst_result.missing_information:
                print(f"    - {item}")
        print()

        # 3. Supply identified patterns into ContextBuilder to retrieve Obsidian knowledge
        obsidian_retriever = ObsidianRetriever()
        builder = ContextBuilder(
            sqlite_retriever=sqlite_retriever,
            obsidian_retriever=obsidian_retriever,
        )

        package: ContextPackage = builder.build(
            requirement_ids=[req_context.requirement_id],
            pattern_names=analyst_result.identified_patterns,
        )

        # 4. Display retrieved Obsidian knowledge
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

        # 5. Display ContextPackage summary
        print("----------------------------------------------------------")
        print("5. CONTEXTPACKAGE SUMMARY")
        print("----------------------------------------------------------")
        print(f"  • Number of Requirements: {len(package.requirements)}")
        print(f"  • Number of Patterns:     {len(package.identified_patterns)}")
        print(f"  • Loaded Files Count:     {obs_res.loaded_files_count}")
        print(f"  • Read Cache Hits:        {obs_res.read_cache_hits}")
        print()

        # 6. Display provenance
        print("----------------------------------------------------------")
        print("6. PROVENANCE")
        print("----------------------------------------------------------")
        print(json.dumps(package.provenance, indent=2))
        print()

        print("==========================================================")
        print("✓ CONTEXTPACKAGE SUCCESSFULLY ASSEMBLED VIA ANALYST MODEL")
        print("✓ READY TO BE PROVIDED TO THE FUTURE REASONING MODEL")
        print("==========================================================")

    except (AnalystError, AnalystValidationError, NonCanonicalPatternError) as e:
        print(f"\n[ERROR] Analyst Model Error: {e}")
        print("Notice: The live Analyst demo requires Ollama daemon running with model 'llama3:latest'.")
        sys.exit(1)
    except SQLiteRetrieverError as e:
        print(f"\n[ERROR] SQLite Retrieval Error: {e}")
        sys.exit(1)
    except ObsidianRetrieverError as e:
        print(f"\n[ERROR] Obsidian Retrieval Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_demo()
