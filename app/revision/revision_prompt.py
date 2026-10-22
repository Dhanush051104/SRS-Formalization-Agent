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
3. Preserve valid definitions: Retain valid proposition definitions (symbols, definitions, and notation), predicate definitions, and domain entities from the previous intermediate_representation unless the Critic identifies a specific, evidence-supported defect or inaccuracy in them. Do not arbitrarily discard, rename, or reinvent valid propositions.
4. Keep valid logical components from the candidate formalization, but correct any errors, missing bounds, false assumptions, or inaccurate mathematical formulations identified by the Critic.
5. Base all formalization decisions strictly on the raw requirement text and official retrieved pattern templates.
6. Incorporate all approved stakeholder clarification resolutions into the formalization. Approved answers are binding and resolve prior ambiguity.
7. No fabricated timing bounds or constraints: If the source requirement is untimed or a parameter is unstated, do not invent artificial timing bounds (e.g. 't_bound') or fabricate constraints. An unstated parameter must not become a fabricated constraint.
8. DO NOT embed definitions into 'formalization': The 'formalization' field must NEVER contain definition statements with ':=' or natural-language prose. Reference only declared symbol identifiers (e.g. G(P_init -> P_install_api)). Definitions belong exclusively in 'intermediate_representation'.
9. Return ONLY a single valid JSON object adhering strictly to the required ReasoningResult schema. Do not include markdown code block ticks outside the JSON object.

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
  "intermediate_representation": {
    "propositions": [
      {
        "symbol": string,
        "definition": string,
        "notation": string,
        "source_reference": string or null,
        "provenance": string
      }
    ],
    "predicates": [
      {
        "name": string,
        "entity": string,
        "arguments": [string],
        "condition_type": string,
        "description": string,
        "formal_expression": string or null,
        "notation": string
      }
    ],
    "entities": [
      {
        "name": string,
        "category": string,
        "description": string
      }
    ],
    "temporal_operators": [string],
    "composition_rules": [string],
    "formula_construction": string,
    "unresolved_parameters": [string]
  },
  "formalization": string (pure mathematical formula referencing declared symbol names; NEVER embed ':=' or prose definitions here),
  "assumptions": [string],
  "unresolved_items": [string],
  "constraint_provenance": [
    {
      "constraint_id": string,
      "statement": string,
      "category": string,
      "source_text": string,
      "justification": string
    }
  ],
  "reasoning_notes": string or null
}
"""


def _format_intermediate_representation(ir: Any) -> str:
    """Format intermediate representation safely for prompt inclusion."""
    if not ir:
        return "  (No intermediate representation provided)"
    if hasattr(ir, "to_dict"):
        ir_dict = ir.to_dict()
    elif isinstance(ir, dict):
        ir_dict = {}
        for k, v in ir.items():
            if isinstance(v, list):
                ir_dict[k] = [
                    item.to_dict() if hasattr(item, "to_dict") else item
                    for item in v
                ]
            elif hasattr(v, "to_dict"):
                ir_dict[k] = v.to_dict()
            else:
                ir_dict[k] = v
    else:
        return f"  {str(ir)}"

    return json.dumps(ir_dict, indent=2)


def _format_constraint_provenance(provenance_list: Any) -> str:
    """Format constraint provenance safely for prompt inclusion."""
    if not provenance_list:
        return "  (No constraint provenance recorded)"

    cleaned = []
    if isinstance(provenance_list, list):
        for item in provenance_list:
            if hasattr(item, "to_dict"):
                cleaned.append(item.to_dict())
            elif isinstance(item, dict):
                cleaned.append(item)
            else:
                cleaned.append(str(item))
    else:
        cleaned = [str(provenance_list)]

    return json.dumps(cleaned, indent=2)


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

    ir = reasoning_result.intermediate_representation
    formula_construction_str = "N/A"
    if isinstance(ir, dict):
        formula_construction_str = ir.get("formula_construction") or "N/A"
    elif hasattr(ir, "formula_construction"):
        formula_construction_str = getattr(ir, "formula_construction") or "N/A"

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

    answered_clarifs = [
        c for c in getattr(context_package, "clarifications", [])
        if c.get("status") == "ANSWERED" and c.get("answer")
    ]
    if answered_clarifs:
        clarifs_lines = []
        for c in answered_clarifs:
            q_id = c.get("question_id", "CLARIF")
            q_text = c.get("question_text", "")
            ans = c.get("answer", "")
            clarifs_lines.append(f"  - [{q_id}] {q_text}\n    Approved Answer: {ans}")
        clarifs_formatted = "\n".join(clarifs_lines)
    else:
        clarifs_formatted = "  (No stakeholder clarifications recorded)"

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
Intermediate Representation:
{_format_intermediate_representation(reasoning_result.intermediate_representation)}
Formula Construction Rationale:
\"\"\"{formula_construction_str}\"\"\"
Candidate Formalization:
\"\"\"{reasoning_result.formalization}\"\"\"
Assumptions: {json.dumps(reasoning_result.assumptions)}
Unresolved Items: {json.dumps(reasoning_result.unresolved_items)}
Constraint Provenance:
{_format_constraint_provenance(reasoning_result.constraint_provenance)}
Reasoning Notes: {reasoning_result.reasoning_notes or 'N/A'}

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
5. STAKEHOLDER CLARIFICATION RESOLUTIONS (BINDING)
==================================================
{clarifs_formatted}

==================================================
6. REVISION TASK INSTRUCTIONS
==================================================
Generate a revised, corrected ReasoningResult JSON object that addresses all Critic findings, resolves missing constraints, corrects unsupported assumptions, incorporates all approved stakeholder clarification resolutions, and produces a rigorous, correct formalization.

IMPORTANT REVISION RULES:
1. Preserve valid intermediate representation: Retain existing proposition definitions (e.g. P1, P2) and predicate definitions from the previous intermediate representation unless the Critic identified specific, evidence-backed defect findings against them.
2. Do not fabricate constraints or timing bounds: If the requirement is untimed or a parameter is unstated in the SRS, DO NOT invent arbitrary timing bounds (such as 't_bound') or artificial temporal deadlines. Keep untimed requirements untimed.
3. Incorporate all approved clarifications into the formalization and intermediate representation.
4. Ensure every proposition used in the final formula is defined in intermediate_representation.propositions with explicit notation (P := ...).
5. The 'formalization' field must contain ONLY the mathematical formula referencing declared symbols (e.g. G(P_init -> P_install_api)). NEVER embed ':=' or natural-language prose definitions inside the formula.

CRITICAL IDENTITY REQUIREMENT: Your output JSON MUST include the root fields:
- requirement_id: {req_id}
- global_number: {global_num}
- srs_id: "{srs_id}"

Output ONLY a valid JSON object.
"""
    return prompt
