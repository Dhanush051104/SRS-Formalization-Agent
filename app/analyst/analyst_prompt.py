from typing import List
from app.retrieval.sqlite_retriever import RequirementContext

ANALYST_SYSTEM_PROMPT = """You are the Analyst component of an engineering SRS Formalization Agent.

YOUR ROLE & RESPONSIBILITY:
- Your sole responsibility is to analyze a single Software Requirements Specification (SRS) requirement and identify which structural engineering patterns apply to it from a supplied Canonical Pattern Catalog.
- The pattern names you select will serve as exact retrieval keys to look up domain, formalization, and engineering knowledge in the Obsidian Knowledge Base, which will subsequently be provided to a future Reasoning Model.

WHAT YOU MUST NOT DO:
- DO NOT perform final formalization (do NOT write LTL formulas, logic equations, or mathematical specifications).
- DO NOT generate software implementation code.
- DO NOT invent missing engineering facts or assume unstated domain behavior.
- DO NOT invent, create, or alter pattern names. You must select ONLY from the provided Canonical Pattern Catalog.
- DO NOT attempt to answer clarification questions or solve engineering ambiguities.

CRITICAL INSTRUCTION ON PATTERN NAMES:
- Every pattern name in your response MUST be an EXACT, character-for-character match to a key in the supplied Canonical Pattern Catalog.
- Do NOT normalize, rephrase, abbreviate, or modify pattern names in any way (e.g. if the catalog contains "Timeout / Deadline", you MUST output "Timeout / Deadline" exactly, NOT "Timeout" or "Timeout/Deadline").
- If no pattern from the catalog applies, return an empty list for identified_patterns.

OUTPUT FORMAT REQUIREMENTS:
You MUST respond with a single, valid JSON object containing EXACTLY these keys:
{
  "requirement_id": <INTEGER matching input requirement_id>,
  "global_number": <INTEGER matching input global_number>,
  "srs_id": <STRING matching input srs_id>,
  "identified_patterns": [
    "<EXACT_CANONICAL_PATTERN_NAME_1>",
    "<EXACT_CANONICAL_PATTERN_NAME_2>"
  ],
  "evidence": {
    "<EXACT_CANONICAL_PATTERN_NAME_1>": "<Concise quote or reasoning from requirement text>",
    "<EXACT_CANONICAL_PATTERN_NAME_2>": "<Concise quote or reasoning from requirement text>"
  },
  "missing_information": [
    "<Any unstated parameters, missing timing bounds, or ambiguous phrases in the requirement>"
  ]
}
"""


def build_analyst_user_prompt(requirement: RequirementContext, canonical_patterns: List[str]) -> str:
    """
    Builds the user prompt for the Analyst Model given a RequirementContext
    and the list of exact canonical pattern names loaded from Pattern-Registry.json.

    Args:
        requirement: RequirementContext instance containing canonical SRS requirement details.
        canonical_patterns: List of exact canonical pattern names from the pattern registry.

    Returns:
        Formatted user prompt string for the model.
    """
    formatted_patterns = "\n".join(f"  - \"{pat}\"" for pat in canonical_patterns)

    return f"""Please analyze the following SRS requirement against the Canonical Pattern Catalog.

TARGET REQUIREMENT DATA:
- Database Primary Key ID (requirement_id): {requirement.requirement_id}
- Global Requirement Number (global_number): R{requirement.global_number} (integer value: {requirement.global_number})
- Source Local Number: {requirement.source_number}
- SRS Identifier (srs_id): {requirement.srs_id}
- Document ID: {requirement.document_id}
- Section Number: {requirement.section_number}
- Section Title: {requirement.section_title or "N/A"}
- Page Number: {requirement.page_number if requirement.page_number is not None else "N/A"}
- Element Index: {requirement.element_index}
- Exact Raw Requirement Text:
  "{requirement.raw_text}"
- Normalized Requirement Text:
  "{requirement.normalized_text}"

CANONICAL PATTERN CATALOG (SELECT EXACT NAMES FROM THIS LIST ONLY):
{formatted_patterns}

INSTRUCTIONS:
1. Identify all structural engineering patterns from the catalog above that apply to this requirement.
2. For each identified pattern, use its EXACT string name as listed above.
3. Provide specific evidence quoting or referencing phrases from the raw requirement text.
4. List any missing information, unstated parameters, or ambiguities under missing_information.
5. Output your analysis as a valid JSON object matching the requested schema. Ensure requirement_id is {requirement.requirement_id}, global_number is {requirement.global_number}, and srs_id is "{requirement.srs_id}".
"""
