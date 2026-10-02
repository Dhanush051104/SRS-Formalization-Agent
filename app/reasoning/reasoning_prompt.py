from typing import List
from app.retrieval.context_builder import ContextPackage

REASONING_SYSTEM_PROMPT = """You are the Reasoning Model of an engineering SRS Formalization Agent.

YOUR ROLE & RESPONSIBILITY:
- Your core responsibility is to translate natural-language Software Requirements Specification (SRS) requirements into precise mathematical representations, predicates, and formal logic (e.g., LTL expressions, metric bounds, predicate equations).
- You receive a structured ContextPackage containing:
  1. The canonical raw requirement text and metadata from SQLite.
  2. Structural patterns identified by the Analyst Model.
  3. Retrieved domain, formalization, and concept knowledge notes loaded from the Obsidian Knowledge Base.
  4. Provenance tracking metadata.

SOURCE FIDELITY RULES (CRITICAL):
- Respect exact source parameters: If the requirement specifies "2.5 seconds", use "2.5 seconds".
- DO NOT invent technical parameters, timing bounds, or thresholds not stated in the SRS or retrieved knowledge.
- If a parameter or timing bound is missing, explicitly list it under "unresolved_items".
- Explicitly separate source facts from your inferences and any necessary engineering assumptions.

WHAT YOU MUST NOT DO:
- DO NOT invent unspecified engineering values or fabricate unstated domain behaviors.
- DO NOT modify the knowledge base or alter pattern definitions.
- DO NOT claim that validation has succeeded — validation is performed by the Critic component.

OUTPUT FORMAT REQUIREMENTS:
You MUST respond with a single, valid JSON object containing EXACTLY these keys:
{
  "requirement_id": <INTEGER matching input requirement_id>,
  "global_number": <INTEGER matching input global_number>,
  "srs_id": <STRING matching input srs_id>,
  "interpretation": "<Clear natural-language summary of the requirement's formal logic>",
  "identified_entities": [
    "<System component, processor, message, or signal name>"
  ],
  "predicates": [
    "<Boolean predicate or state expression, e.g. failed(FCP), synced(FCP)>"
  ],
  "conditions": [
    "<Trigger or precondition statement>"
  ],
  "actions": [
    "<Action or postcondition statement>"
  ],
  "temporal_constraints": [
    "<Bounded time or sequence constraint, e.g. within 1 second, 2.5 seconds timeout>"
  ],
  "mathematical_constraints": [
    "<Derived metric or threshold equation, e.g. time_since_loss > 2.5s>"
  ],
  "dependencies": [
    "<Prerequisite requirement SRS ID or component dependency>"
  ],
  "formalization": "<Candidate formal mathematical logic string, e.g. G(failed_sync_2.5s -> F[0,1s] send_vme_reset)>",
  "assumptions": [
    "<Explicit engineering assumptions made during formalization>"
  ],
  "unresolved_items": [
    "<Unstated parameters, missing bounds, or ambiguities requiring clarification>"
  ],
  "reasoning_notes": "<Additional notes regarding formalization strategy or pattern application>"
}
"""


def build_reasoning_user_prompt(context_package: ContextPackage) -> str:
    """
    Serializes a ContextPackage into a clean, structured user prompt for the Reasoning Model.

    Args:
        context_package: ContextPackage instance containing requirements, patterns, and retrieved knowledge.

    Returns:
        Formatted user prompt string.
    """
    req = context_package.requirements[0] if context_package.requirements else None

    if not req:
        raise ValueError("ContextPackage must contain at least one RequirementContext.")

    # Format Identified Patterns
    patterns_str = "\n".join(f"  - {pat}" for pat in context_package.identified_patterns) or "  - None identified"

    # Format Retrieved Obsidian Knowledge
    obs = context_package.obsidian_knowledge
    retrieved_knowledge_blocks: List[str] = []

    for item in obs.pattern_items:
        block = f"### Pattern: {item.requested_pattern} (ID: {item.pattern_id})\n"
        block += f"File: {item.pattern_file_path}\n"
        if item.pattern_note and item.pattern_note.content:
            # Include pattern note content (truncated if excessively long)
            content = item.pattern_note.content.strip()
            block += f"Content:\n{content}\n"

        if item.formalization_notes:
            block += "Formalization Notes:\n"
            for fn in item.formalization_notes:
                block += f"  - [{fn.file_path}]\n"
                if fn.content:
                    block += f"    {fn.content.strip()[:600]}\n"

        if item.concept_notes:
            block += "Concept Notes:\n"
            for cn in item.concept_notes:
                block += f"  - [{cn.file_path}]\n"
                if cn.content:
                    block += f"    {cn.content.strip()[:600]}\n"

        retrieved_knowledge_blocks.append(block)

    knowledge_str = "\n".join(retrieved_knowledge_blocks) if retrieved_knowledge_blocks else "No Obsidian notes loaded."

    return f"""Please analyze and formalize the following SRS requirement using the provided ContextPackage data.

==========================================================
1. CANONICAL SRS REQUIREMENT DATA
==========================================================
- Requirement ID:        {req.requirement_id}
- Global Number:         R{req.global_number} (integer: {req.global_number})
- SRS Identifier:        {req.srs_id}
- Source Local Number:   {req.source_number}
- Section:               {req.section_number} ({req.section_title or 'N/A'})
- Page Number:           {req.page_number if req.page_number is not None else 'N/A'}
- Element Index:         {req.element_index}
- Exact Raw Text:
  "{req.raw_text}"
- Normalized Text:
  "{req.normalized_text}"

==========================================================
2. ANALYST IDENTIFIED STRUCTURAL PATTERNS
==========================================================
{patterns_str}

==========================================================
3. RETRIEVED DOMAIN, FORMALIZATION & CONCEPT KNOWLEDGE
==========================================================
{knowledge_str}

==========================================================
INSTRUCTIONS
==========================================================
1. Analyze the requirement logic using the raw text and retrieved Obsidian knowledge.
2. Identify entities, predicates, conditions, actions, temporal constraints, mathematical constraints, and dependencies.
3. Formulate a candidate formal mathematical logic statement (e.g. LTL, predicate logic equation, metric constraint) under "formalization".
4. Explicitly list any assumptions under "assumptions" and unstated/missing parameters under "unresolved_items".
5. Ensure requirement_id is {req.requirement_id}, global_number is {req.global_number}, and srs_id is "{req.srs_id}".
6. Output a single valid JSON object matching the requested schema.
"""
