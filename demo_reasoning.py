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
from app.reasoning import (
    OllamaReasoning,
    ReasoningError,
    ReasoningResult,
    ReasoningValidationError,
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
    print("      SRS FORMALIZATION AGENT — REASONING MODEL DEMO      ")
    print("==========================================================")
    print()

    target_requirement_id = 8  # Requirement R8 / [SRS178]

    try:
        # 1. Retrieve canonical requirement context from SQLite
        sqlite_retriever = SQLiteRetriever()
        req_context = sqlite_retriever.get_requirement_by_id(target_requirement_id)

        print("----------------------------------------------------------")
        print("1. TARGET REQUIREMENT")
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
        print("2. PATTERNS IDENTIFIED BY ANALYST MODEL")
        print("----------------------------------------------------------")
        if not analyst_result.identified_patterns:
            print("  (No canonical patterns identified for this requirement)")
        else:
            for idx, name in enumerate(analyst_result.identified_patterns, 1):
                evidence = analyst_result.evidence.get(name, "No evidence provided")
                print(f"  {idx}. {name}")
                print(f"     Evidence: \"{evidence}\"")
        print()

        # 3. Supply identified patterns into ContextBuilder to retrieve Obsidian knowledge
        print("Retrieving Obsidian domain & formalization knowledge...")
        obsidian_retriever = ObsidianRetriever()
        builder = ContextBuilder(
            sqlite_retriever=sqlite_retriever,
            obsidian_retriever=obsidian_retriever,
        )

        context_package: ContextPackage = builder.build(
            requirement_ids=[req_context.requirement_id],
            pattern_names=analyst_result.identified_patterns,
        )

        print("----------------------------------------------------------")
        print("3. CONTEXTPACKAGE SUMMARY")
        print("----------------------------------------------------------")
        obs_res = context_package.obsidian_knowledge
        print(f"  • Requirements Count:    {len(context_package.requirements)}")
        print(f"  • Patterns Count:        {len(context_package.identified_patterns)}")
        print(f"  • Obsidian Notes Loaded: {obs_res.loaded_files_count}")
        print(f"  • Read Cache Hits:       {obs_res.read_cache_hits}")
        print()

        # 4. Invoke local Llama 3 Reasoning Model via Ollama
        print("Running Llama 3 Reasoning Model via Ollama...")
        reasoner = OllamaReasoning(model="llama3:latest")
        reasoning_result: ReasoningResult = reasoner.reason(context_package)

        print("==========================================================")
        print("4. REASONING MODEL FORMALIZATION")
        print("==========================================================")
        print(f"Requirement:               R{reasoning_result.global_number} / {reasoning_result.srs_id}")
        print()
        print(f"Interpretation:\n  {reasoning_result.interpretation}")
        print()

        print("Identified Entities:")
        if reasoning_result.identified_entities:
            for item in reasoning_result.identified_entities:
                print(f"  • {item}")
        else:
            print("  (None listed)")
        print()

        print("Predicates:")
        if reasoning_result.predicates:
            for item in reasoning_result.predicates:
                print(f"  • {item}")
        else:
            print("  (None listed)")
        print()

        print("Conditions:")
        if reasoning_result.conditions:
            for item in reasoning_result.conditions:
                print(f"  • {item}")
        else:
            print("  (None listed)")
        print()

        print("Actions:")
        if reasoning_result.actions:
            for item in reasoning_result.actions:
                print(f"  • {item}")
        else:
            print("  (None listed)")
        print()

        print("Temporal Constraints:")
        if reasoning_result.temporal_constraints:
            for item in reasoning_result.temporal_constraints:
                print(f"  • {item}")
        else:
            print("  (None listed)")
        print()

        print("Mathematical Constraints:")
        if reasoning_result.mathematical_constraints:
            for item in reasoning_result.mathematical_constraints:
                print(f"  • {item}")
        else:
            print("  (None listed)")
        print()

        print("Dependencies:")
        if reasoning_result.dependencies:
            for item in reasoning_result.dependencies:
                print(f"  • {item}")
        else:
            print("  (None listed)")
        print()

        print(f"Formalization Statement:\n  {reasoning_result.formalization}")
        print()

        print("Assumptions:")
        if reasoning_result.assumptions:
            for item in reasoning_result.assumptions:
                print(f"  • {item}")
        else:
            print("  (None listed)")
        print()

        print("Unresolved Items / Missing Information:")
        if reasoning_result.unresolved_items:
            for item in reasoning_result.unresolved_items:
                print(f"  • {item}")
        else:
            print("  (None identified)")
        print()

        if reasoning_result.reasoning_notes:
            print(f"Reasoning Notes:\n  {reasoning_result.reasoning_notes}")
            print()

        print("----------------------------------------------------------")
        print("5. PROVENANCE")
        print("----------------------------------------------------------")
        print(json.dumps(reasoning_result.provenance, indent=2))
        print()

        print("==========================================================")
        print("✓ END-TO-END PIPELINE SUCCESSFULLY EXECUTED")
        print("  SRS -> SQLite -> Analyst -> Obsidian -> ContextPackage -> Reasoning Model")
        print("==========================================================")

    except (AnalystError, AnalystValidationError, NonCanonicalPatternError) as e:
        print(f"\n[ERROR] Analyst Model Error: {e}")
        print("Notice: The live demo requires Ollama daemon running with model 'llama3:latest'.")
        sys.exit(1)
    except (ReasoningError, ReasoningValidationError) as e:
        print(f"\n[ERROR] Reasoning Model Error: {e}")
        print("Notice: The live demo requires Ollama daemon running with model 'llama3:latest'.")
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
