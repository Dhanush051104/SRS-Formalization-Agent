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
from app.critic import (
    CriticError,
    CriticResult,
    CriticValidationError,
    OllamaCritic,
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
    print("      SRS FORMALIZATION AGENT — CRITIC DEMO               ")
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
        print("1/4 Running Llama 3 Analyst Model...")
        analyst = OllamaAnalyst(model="llama3:latest")
        analyst_result: AnalystResult = analyst.analyze(req_context)

        # 3. Supply identified patterns into ContextBuilder to retrieve Obsidian knowledge
        print("2/4 Retrieving Obsidian domain & formalization knowledge...")
        obsidian_retriever = ObsidianRetriever()
        builder = ContextBuilder(
            sqlite_retriever=sqlite_retriever,
            obsidian_retriever=obsidian_retriever,
        )
        context_package: ContextPackage = builder.build(
            requirement_ids=[req_context.requirement_id],
            pattern_names=analyst_result.identified_patterns,
        )

        # 4. Invoke local Llama 3 Reasoning Model via Ollama
        print("3/4 Running Llama 3 Reasoning Model...")
        reasoner = OllamaReasoning(model="llama3:latest")
        reasoning_result: ReasoningResult = reasoner.reason(context_package)

        # 5. Invoke local Llama 3 Critic Model via Ollama
        print("4/4 Running Llama 3 Critic / Verification Model...")
        critic = OllamaCritic(model="llama3:latest")
        critic_result: CriticResult = critic.critique(context_package, reasoning_result)

        print()
        print("==========================================================")
        print("CRITIC / VALIDATION MODEL EVALUATION")
        print("==========================================================")
        print(f"Requirement:               R{critic_result.global_number} / {critic_result.srs_id}")
        print(f"Status:                    {critic_result.status}")
        print(f"Revision Required:         {'YES' if critic_result.revision_required else 'NO'}")
        print()

        print("Candidate Formalization Evaluated:")
        print(f"  \"{reasoning_result.formalization}\"")
        print()

        print("Pattern Coverage:")
        cov = critic_result.pattern_coverage
        if isinstance(cov, dict):
            covered = cov.get("covered_patterns", [])
            unaddressed = cov.get("unaddressed_patterns", [])
            print(f"  • Covered Patterns:     {', '.join(covered) if covered else 'None'}")
            print(f"  • Unaddressed Patterns: {', '.join(unaddressed) if unaddressed else 'None'}")
        else:
            print(f"  {cov}")
        print()

        print("Structured Findings:")
        if critic_result.findings:
            for idx, f in enumerate(critic_result.findings, 1):
                print(f"  [{idx}] [{f.severity}] {f.category}")
                print(f"      Description:       {f.description}")
                if f.source_evidence:
                    print(f"      Source Evidence:   \"{f.source_evidence}\"")
                if f.reasoning_evidence:
                    print(f"      Reasoning Evidence:\"{f.reasoning_evidence}\"")
                if f.recommendation:
                    print(f"      Recommendation:    {f.recommendation}")
                print()
        else:
            print("  (No specific findings flagged)")
            print()

        print("Missing Constraints:")
        if critic_result.missing_constraints:
            for item in critic_result.missing_constraints:
                print(f"  • {item}")
        else:
            print("  (None identified)")
        print()

        print("Unsupported Assumptions:")
        if critic_result.unsupported_assumptions:
            for item in critic_result.unsupported_assumptions:
                print(f"  • {item}")
        else:
            print("  (None identified)")
        print()

        print("Contradictions:")
        if critic_result.contradictions:
            for item in critic_result.contradictions:
                print(f"  • {item}")
        else:
            print("  (None identified)")
        print()

        print("Traceability Issues:")
        if critic_result.traceability_issues:
            for item in critic_result.traceability_issues:
                print(f"  • {item}")
        else:
            print("  (None identified)")
        print()

        print("Formalization Assessment:")
        print(f"  {critic_result.formalization_assessment}")
        print()

        print("Summary Verdict:")
        print(f"  {critic_result.summary}")
        print()

        print("----------------------------------------------------------")
        print("PROVENANCE")
        print("----------------------------------------------------------")
        print(json.dumps(critic_result.provenance, indent=2))
        print()

        print("==========================================================")
        print("✓ CRITIC / VALIDATION MODEL COMPLETED SUCCESSFULLY")
        print("==========================================================")

    except (AnalystError, AnalystValidationError, NonCanonicalPatternError) as e:
        print(f"\n[ERROR] Analyst Model Error: {e}")
        print("Notice: The live demo requires Ollama daemon running with model 'llama3:latest'.")
        sys.exit(1)
    except (ReasoningError, ReasoningValidationError) as e:
        print(f"\n[ERROR] Reasoning Model Error: {e}")
        print("Notice: The live demo requires Ollama daemon running with model 'llama3:latest'.")
        sys.exit(1)
    except (CriticError, CriticValidationError) as e:
        print(f"\n[ERROR] Critic Model Error: {e}")
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
