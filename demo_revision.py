#!/usr/bin/env python3
"""
demo_revision.py

Standalone demonstration script for the SRS Formalization Agent Revision Loop.
Executes the end-to-end pipeline:
  SQLite -> ContextBuilder -> Analyst -> Obsidian -> ContextPackage -> ReasoningModel -> CriticModel -> RevisionManager

Prints step-by-step terminal demonstration showing initial candidate formalization,
Critic findings, dynamic prompt construction, and final convergence or termination.
"""

import sys
from pathlib import Path

# Add project root directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.analyst.ollama_analyst import OllamaAnalyst
from app.critic.ollama_critic import OllamaCritic
from app.reasoning.ollama_reasoning import OllamaReasoning
from app.retrieval.context_builder import ContextBuilder
from app.revision.revision_manager import RevisionManager


def main():
    print("=" * 70)
    print("SRS FORMALIZATION AGENT — REVISION LOOP DEMO")
    print("=" * 70)

    # 1. Target Requirement Setup & Retrieval
    requirement_id = 8
    print(f"\n[1. TARGET SELECTION & SQLITE RETRIEVAL]")
    print(f"Target Requirement Database Primary Key ID: {requirement_id}")

    from app.retrieval.sqlite_retriever import SQLiteRetriever
    sqlite_retriever = SQLiteRetriever()
    req_context = sqlite_retriever.get_requirement_by_id(requirement_id)

    # 2. Analyst Pattern Identification
    print("\n[2. ANALYST MODEL IDENTIFICATION]")
    analyst = OllamaAnalyst()
    print("Running Llama 3 Analyst Model to identify structural engineering patterns...")
    analyst_result = analyst.analyze(req_context)

    print(f"Requirement SRS ID: {analyst_result.srs_id}")
    print("Identified Patterns:")
    for idx, p in enumerate(analyst_result.identified_patterns, 1):
        print(f"  {idx}. {p}")

    # 3. Deterministic Knowledge Retrieval & Context Assembly
    print("\n[3. CONTEXT PACKAGE ASSEMBLY]")
    builder = ContextBuilder(sqlite_retriever=sqlite_retriever)
    context_package = builder.build([requirement_id], analyst_result.identified_patterns)

    req = context_package.requirements[0]
    print(f"SRS Requirement ID : {req.srs_id}")
    print(f"Global Requirement #: R{req.global_number}")
    print(f"Section             : {req.section_number} - {req.section_title}")
    print(f"Raw Requirement Text:\n  \"{req.raw_text}\"")

    # 4. Instantiate Models & Revision Manager
    print("\n[4. REVISION LOOP INITIALIZATION]")
    reasoning_model = OllamaReasoning()
    critic_model = OllamaCritic()
    max_iterations = 3

    manager = RevisionManager(
        reasoning_model=reasoning_model,
        critic_model=critic_model,
        max_iterations=max_iterations,
    )
    print(f"RevisionManager initialized with max_iterations = {max_iterations}")

    # 5. Run Bounded Revision Loop
    print("\n[5. EXECUTING BOUNDED REVISION LOOP]")
    print("-" * 70)
    revision_result = manager.run_revision_loop(context_package)

    # 6. Print Iteration History
    for entry in revision_result.history:
        print(f"\n>>> ITERATION {entry.iteration} <<<")
        rr = entry.reasoning_result
        cr = entry.critic_result

        print("\n--- REASONING MODEL OUTPUT ---")
        print(f"Interpretation : {rr.interpretation}")
        print(f"Entities       : {rr.identified_entities}")
        print(f"Predicates     : {rr.predicates}")
        print(f"Conditions     : {rr.conditions}")
        print(f"Actions        : {rr.actions}")
        print(f"Temporal Bounds: {rr.temporal_constraints}")
        print(f"Math Constraints: {rr.mathematical_constraints}")
        print(f"Formalization  :\n  {rr.formalization}")

        print("\n--- CRITIC MODEL VERIFICATION ---")
        print(f"Critic Status  : {cr.status}")
        print(f"Summary        : {cr.summary}")
        if cr.findings:
            print("Detailed Findings:")
            for f_idx, f in enumerate(cr.findings, 1):
                print(f"  [{f_idx}] [{f.severity}] Category: {f.category}")
                print(f"      Description   : {f.description}")
                if f.recommendation:
                    print(f"      Recommendation: {f.recommendation}")
        if cr.missing_constraints:
            print(f"Missing Constraints: {cr.missing_constraints}")
        if cr.unsupported_assumptions:
            print(f"Unsupported Assumptions: {cr.unsupported_assumptions}")

        if entry.revision_prompt_used:
            print("\n--- REVISION PROMPT FORWARDED TO REASONING MODEL ---")
            snippet = entry.revision_prompt_used[:350].replace("\n", "\n  ")
            print(f"  {snippet}...\n  [Truncated for terminal clarity]")

        print("-" * 70)

    # 7. Final Summary Section
    print("\n==================================================")
    print("REVISION LOOP DEMO RESULT SUMMARY")
    print("==================================================")
    print(f"Target Requirement   : R{revision_result.global_number} ({revision_result.srs_id})")
    print(f"Final Status         : {revision_result.status}")
    print(f"Termination Reason   : {revision_result.termination_reason}")
    print(f"Iterations Conducted : {revision_result.iterations_conducted} / {revision_result.max_iterations}")
    print(f"\nFinal Formalization  :\n  {revision_result.final_reasoning_result.formalization}")
    print(f"\nFinal Critic Assessment:\n  {revision_result.final_critic_result.summary}")
    print("==================================================")


if __name__ == "__main__":
    main()
