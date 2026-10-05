import json
from typing import Any, Dict

from app.critic.schemas import CriticResult
from app.reasoning.schemas import ReasoningResult
from app.retrieval.context_builder import ContextPackage

REVISION_SYSTEM_PROMPT = """You are the formalization reasoning model for an automated SRS (Software Requirements Specification) formalization agent.

Your task is to REVISE and IMPROVE a candidate formalization based on explicit verification feedback provided by an independent Critic Model.

CRITICAL INSTRUCTIONS:
1. Preserve requirement identity fields exactly: requirement_id, global_number, srs_id.
2. Carefully address every finding, missing constraint, unsupported assumption, contradiction, or traceability issue highlighted in the Critic feedback.
3. Keep valid logical components from the candidate formalization, but correct any errors, missing bounds, false assumptions, or inaccurate mathematical formulations.
4. Base all formalization decisions strictly on the raw requirement text and official retrieved pattern templates.
5. Return ONLY a single valid JSON object adhering strictly to the required ReasoningResult schema. Do not include markdown code block ticks outside the JSON object.

JSON SCHEMA REQUIREMENT:
{
  "requirement_id": integer,
  "global_number": integer,
  "srs_id": string,
  "interpretation": string,
  "identified_entities": [string],
  "predicates": [string],
  "conditions": [string],
  "actions": [string],
  "temporal_constraints": [string],
  "mathematical_constraints": [string],
  "dependencies": [string],
  "formalization": string,
  "assumptions": [string],
  "unresolved_items": [string],
  "reasoning_notes": string or null
}
"""


def build_revision_user_prompt(
    context_package: ContextPackage,
    reasoning_result: ReasoningResult,
    critic_result: CriticResult,
) -> str:
    """
    Builds a detailed user prompt for the Reasoning Model combining original context,
    the candidate reasoning result, and full Critic feedback.

    Args:
        context_package: ContextPackage instance.
        reasoning_result: Previous candidate ReasoningResult instance.
        critic_result: CriticResult instance containing detailed feedback.

    Returns:
        Formatted prompt string for model execution.
    """
    req = context_package.requirements[0] if context_package.requirements else None
    req_id = req.requirement_id if req else reasoning_result.requirement_id
    global_num = req.global_number if req else reasoning_result.global_number
    srs_id = req.srs_id if req else reasoning_result.srs_id
    raw_text = req.raw_text if req else ""
    sec_num = req.section_number if req else ""
    sec_title = req.section_title if req else ""

    retrieved_patterns_str = ""
    if context_package.obsidian_knowledge and hasattr(context_package.obsidian_knowledge, "pattern_items") and context_package.obsidian_knowledge.pattern_items:
        for p in context_package.obsidian_knowledge.pattern_items:
            retrieved_patterns_str += f"\n--- Pattern: {p.requested_pattern} ({p.pattern_id}) ---\n"
            retrieved_patterns_str += f"File: {p.pattern_file_path}\n"
            retrieved_patterns_str += f"Content:\n{p.pattern_note.content}\n"
    else:
        retrieved_patterns_str = "(No pattern templates retrieved)"

    findings_formatted = ""
    if critic_result.findings:
        for idx, f in enumerate(critic_result.findings, 1):
            findings_formatted += (
                f"\n  Finding {idx} [{f.severity}] (Category: {f.category}):\n"
                f"    - Description: {f.description}\n"
            )
            if f.source_evidence:
                findings_formatted += f"    - Source Evidence: {f.source_evidence}\n"
            if f.reasoning_evidence:
                findings_formatted += f"    - Candidate Reasoning Evidence: {f.reasoning_evidence}\n"
            if f.recommendation:
                findings_formatted += f"    - Recommendation: {f.recommendation}\n"
    else:
        findings_formatted = "  (No granular findings)"

    missing_constraints_str = (
        "\n".join(f"  - {c}" for c in critic_result.missing_constraints)
        if critic_result.missing_constraints
        else "  (None)"
    )
    unsupported_assumptions_str = (
        "\n".join(f"  - {a}" for a in critic_result.unsupported_assumptions)
        if critic_result.unsupported_assumptions
        else "  (None)"
    )
    contradictions_str = (
        "\n".join(f"  - {c}" for c in critic_result.contradictions)
        if critic_result.contradictions
        else "  (None)"
    )
    traceability_issues_str = (
        "\n".join(f"  - {t}" for t in critic_result.traceability_issues)
        if critic_result.traceability_issues
        else "  (None)"
    )

    prompt = f"""REVISION REQUEST FOR REQUIREMENT {srs_id}

==================================================
1. ORIGINAL TARGET REQUIREMENT CONTEXT
==================================================
Requirement ID: {req_id}
Global Number: {global_num}
SRS ID: {srs_id}
Section Number: {sec_num}
Section Title: {sec_title}

Raw Requirement Text:
\"\"\"{raw_text}\"\"\"

==================================================
2. RETRIEVED PATTERN KNOWLEDGE
==================================================
{retrieved_patterns_str}

==================================================
3. PREVIOUS CANDIDATE FORMALIZATION (BEING REVISED)
==================================================
Interpretation: {reasoning_result.interpretation}
Identified Entities: {json.dumps(reasoning_result.identified_entities)}
Predicates: {json.dumps(reasoning_result.predicates)}
Conditions: {json.dumps(reasoning_result.conditions)}
Actions: {json.dumps(reasoning_result.actions)}
Temporal Constraints: {json.dumps(reasoning_result.temporal_constraints)}
Mathematical Constraints: {json.dumps(reasoning_result.mathematical_constraints)}
Dependencies: {json.dumps(reasoning_result.dependencies)}
Candidate Formalization:
\"\"\"{reasoning_result.formalization}\"\"\"
Assumptions: {json.dumps(reasoning_result.assumptions)}
Unresolved Items: {json.dumps(reasoning_result.unresolved_items)}

==================================================
4. CRITIC MODEL VERIFICATION FEEDBACK
==================================================
Status: {critic_result.status}
Summary: {critic_result.summary}
Formalization Assessment: {critic_result.formalization_assessment}

Detailed Findings:
{findings_formatted}

Missing Constraints:
{missing_constraints_str}

Unsupported Assumptions:
{unsupported_assumptions_str}

Contradictions Identified:
{contradictions_str}

Traceability Issues:
{traceability_issues_str}

==================================================
5. REVISION TASK INSTRUCTIONS
==================================================
Generate a revised, corrected ReasoningResult JSON object that addresses all Critic findings, resolves missing constraints, corrects unsupported assumptions, and produces a rigorous, correct formalization.

Ensure exact requirement identity output:
- requirement_id: {req_id}
- global_number: {global_num}
- srs_id: "{srs_id}"

Output ONLY a valid JSON object.
"""
    return prompt
