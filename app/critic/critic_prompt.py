import json
from typing import Any, Dict
from app.retrieval.context_builder import ContextPackage
from app.reasoning.schemas import ReasoningResult

CRITIC_SYSTEM_PROMPT = """You are the independent Critic & Verification Model of an engineering SRS Formalization Agent.

YOUR ROLE & RESPONSIBILITY:
- Your sole responsibility is to independently critique a candidate ReasoningResult against the original ContextPackage and original SRS requirement text.
- You must verify that the reasoning and mathematical formalization accurately preserve all source constraints, timing bounds, actors, conditions, actions, and dependencies without fabricating unstated facts or dropping specified requirements.

EVALUATION CRITERIA:
1. TIMING PRESERVATION: Verify that exact timing bounds (e.g. "2.5 seconds", "within 1 second") and temporal ordering are fully preserved. Flag any modified, dropped, or substituted timing bounds as WARNING or ERROR.
2. ACTOR & ACTION PRESERVATION: Verify that specified actors (e.g. "surviving triplex", "failed FCP processor") and actions (e.g. "send single voted VMEbus reset through NE") are preserved.
3. CONDITIONAL STRUCTURE: Verify that preconditions, triggers, and postconditions are fully represented in the interpretation and formalization.
4. PATTERN COVERAGE: Compare the Analyst-identified patterns against the ReasoningResult. Determine whether each pattern's meaning is represented in the logical structure or temporal bounds.
5. ASSUMPTION AUDIT: Inspect every listed assumption. Flag unnecessary assumptions (e.g., restating explicit SRS facts as assumptions) or unsupported domain assumptions.
6. SOURCE FIDELITY: Flag any invented parameters, fabricated thresholds, or unsupported facts not present in the SRS text or retrieved knowledge.
7. TRACEABILITY & CONTRADICTIONS: Flag formalization expressions that lack clear source basis, or contradictions between requirement text and formalization.

STATUS ASSIGNMENT:
- "PASS": No material errors or missing constraints detected.
- "NEEDS_REVISION": One or more correctable discrepancies, missing bounds, unsupported assumptions, or unaddressed patterns exist.
- "BLOCKED": Required information is missing or contradictory enough that reliable formalization cannot proceed.

FINDINGS STRUCTURE:
Provide a list of structured findings. Each finding must contain:
- "category": (e.g. "Timing Preservation", "Actor Preservation", "Conditional Structure", "Pattern Coverage", "Unsupported Assumption", "Formalization Consistency", "Traceability")
- "severity": "INFO", "WARNING", or "ERROR"
- "description": Clear explanation of the discrepancy
- "source_evidence": Quote from original requirement text
- "reasoning_evidence": Quote from candidate ReasoningResult
- "recommendation": Concrete advice for revision

OUTPUT FORMAT REQUIREMENTS:
You MUST respond with a single, valid JSON object containing EXACTLY these keys:
{
  "requirement_id": <INTEGER matching input requirement_id>,
  "global_number": <INTEGER matching input global_number>,
  "srs_id": <STRING matching input srs_id>,
  "status": "PASS" | "NEEDS_REVISION" | "BLOCKED",
  "findings": [
    {
      "category": "<Category Name>",
      "severity": "INFO" | "WARNING" | "ERROR",
      "description": "<Explanation of issue>",
      "source_evidence": "<Quote from SRS>",
      "reasoning_evidence": "<Quote from ReasoningResult>",
      "recommendation": "<How to fix>"
    }
  ],
  "missing_constraints": [
    "<Any dropped or unaddressed timing/condition constraint from SRS>"
  ],
  "unsupported_assumptions": [
    "<Any assumption that is unnecessary or unsupported>"
  ],
  "contradictions": [
    "<Any direct conflict between SRS text and candidate reasoning>"
  ],
  "traceability_issues": [
    "<Formalization parts with no clear source origin>"
  ],
  "pattern_coverage": {
    "covered_patterns": ["<Pattern 1>", "<Pattern 2>"],
    "unaddressed_patterns": ["<Pattern 3>"]
  },
  "formalization_assessment": "<Overall critique of the candidate formal logic statement>",
  "revision_required": true | false,
  "summary": "<Concise summary of Critic evaluation and verdict>"
}
"""


def build_critic_user_prompt(
    context_package: ContextPackage,
    reasoning_result: ReasoningResult,
) -> str:
    """
    Serializes a ContextPackage and ReasoningResult into a structured user prompt for the Critic Model.

    Args:
        context_package: ContextPackage containing canonical SRS data & retrieved knowledge.
        reasoning_result: Candidate ReasoningResult to critique.

    Returns:
        Formatted user prompt string for the model.
    """
    req = context_package.requirements[0] if context_package.requirements else None
    if not req:
        raise ValueError("ContextPackage must contain at least one RequirementContext.")

    patterns_str = "\n".join(f"  - {pat}" for pat in context_package.identified_patterns) or "  - None identified"

    return f"""Please perform an independent verification and critique of the candidate ReasoningResult against the original ContextPackage.

==========================================================
1. AUTHORITATIVE SRS REQUIREMENT DATA (SOURCE TRUTH)
==========================================================
- Requirement ID:        {req.requirement_id}
- Global Number:         R{req.global_number} (integer: {req.global_number})
- SRS Identifier:        {req.srs_id}
- Section:               {req.section_number} ({req.section_title or 'N/A'})
- Page Number:           {req.page_number if req.page_number is not None else 'N/A'}
- Exact Raw Text:
  "{req.raw_text}"
- Normalized Text:
  "{req.normalized_text}"

ANALYST IDENTIFIED PATTERNS:
{patterns_str}

==========================================================
2. CANDIDATE REASONING RESULT TO CRITIQUE
==========================================================
- Interpretation:
  "{reasoning_result.interpretation}"

- Identified Entities:
  {json.dumps(reasoning_result.identified_entities, indent=2)}

- Predicates:
  {json.dumps(reasoning_result.predicates, indent=2)}

- Conditions:
  {json.dumps(reasoning_result.conditions, indent=2)}

- Actions:
  {json.dumps(reasoning_result.actions, indent=2)}

- Temporal Constraints:
  {json.dumps(reasoning_result.temporal_constraints, indent=2)}

- Mathematical Constraints:
  {json.dumps(reasoning_result.mathematical_constraints, indent=2)}

- Dependencies:
  {json.dumps(reasoning_result.dependencies, indent=2)}

- Candidate Formalization Statement:
  "{reasoning_result.formalization}"

- Assumptions:
  {json.dumps(reasoning_result.assumptions, indent=2)}

- Unresolved Items / Missing Information:
  {json.dumps(reasoning_result.unresolved_items, indent=2)}

- Reasoning Notes:
  "{reasoning_result.reasoning_notes or 'N/A'}"

==========================================================
INSTRUCTIONS
==========================================================
1. Inspect the candidate ReasoningResult against the raw requirement text and identified patterns.
2. Verify timing preservation (e.g. check whether 2.5s and 1s bounds were both preserved in conditions/temporal constraints/formalization).
3. Verify actor and action preservation.
4. Evaluate pattern coverage: check if identified patterns ({context_package.identified_patterns}) are represented.
5. Audit assumptions: identify unnecessary or unsupported assumptions.
6. Identify any missing constraints, contradictions, or traceability issues.
7. Assign status ("PASS", "NEEDS_REVISION", or "BLOCKED") and set revision_required.
8. Output your critique as a single valid JSON object matching the requested schema. Ensure requirement_id is {req.requirement_id}, global_number is {req.global_number}, and srs_id is "{req.srs_id}".
"""
