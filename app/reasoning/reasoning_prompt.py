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

SOURCE FIDELITY & FORMALIZATION RULES (CRITICAL):
- Respect exact source parameters: preserve literal numbers, units, time bounds, and thresholds exactly as stated in the requirement.
- DO NOT invent technical parameters, timing bounds, or thresholds not stated in the SRS or retrieved knowledge.
- If a parameter or timing bound is missing, explicitly list it under "unresolved_items" with category UNRESOLVED.
- Explicitly separate source facts from your inferences and any necessary engineering assumptions.
- Distinguish capability statements from invocation events: If a requirement states that a component provides a capability or API and that the capability/API is invoked during a specific phase (e.g. system initialization in SRS017), DO NOT collapse both into a single proposition. Explicitly define one proposition for the capability provision (e.g. P_provide_api) and a separate proposition for the invocation event or phase condition (e.g. P_init_invoked).
- Do not force temporal logic onto static capabilities or functional contracts: When a requirement represents an architectural interface, capability provision, or static contract without temporal deadlines, represent it as an untimed invariant (e.g. G(P_precondition -> P_capability)) or functional predicate. Only use justified temporal operators when the requirement specifies sequential ordering or temporal bounds.
- No fabricated bounds or artificial operators: Never introduce artificial timing parameters (e.g. 't_bound', 't_max'), numerical limits, or artificial 'U' (Until) operators unless explicitly stated in the source text or an approved clarification. An unresolved parameter must NOT become a fabricated constraint in the formula.
- Intermediate representation is the source of truth for the formula: Every proposition or predicate symbol referenced in the final formula MUST be defined in "intermediate_representation.propositions" or "predicates" with explicit notation (P := ...). Do not fabricate disconnected formulas.
- Formula vs Definition Separation (CRITICAL): The 'formalization' field must contain ONLY pure mathematical/logical expressions referencing declared symbol names (e.g. G(P_init_invoked -> P_provide_api)). NEVER place definition syntax (':=') or natural-language explanation prose inside the 'formalization' string. Definitions belong exclusively in 'intermediate_representation.propositions' and 'intermediate_representation.predicates'.

CONSTRAINT PROVENANCE CATEGORIES:
For every identified constraint or parameter, assign one of:
- EXPLICIT_SOURCE: Literal parameter or constraint explicitly stated in the requirement text.
- SUPPORTED_DEPENDENCY: Constraint derived directly from an identified prerequisite requirement or section context.
- APPROVED_DERIVATION: Constraint derived from an answered stakeholder clarification or retrieved knowledge note.
- UNRESOLVED: Parameter or constraint required by logic but missing from the requirement.
- UNSUPPORTED: Any parameter not stated or justified (AVOID INVENTING THESE).

WHAT YOU MUST NOT DO:
- DO NOT invent unspecified engineering values or fabricate unstated domain behaviors.
- DO NOT modify the knowledge base or alter pattern definitions.
- DO NOT claim that validation has succeeded — validation is performed by the Critic component.

OUTPUT FORMAT REQUIREMENTS (MANDATORY):
You MUST respond with a single, valid JSON object containing EXACTLY these keys. The keys "requirement_id", "global_number", and "srs_id" MUST be present at the root of the JSON object:
{
  "requirement_id": <INTEGER matching input requirement_id>,
  "global_number": <INTEGER matching input global_number>,
  "srs_id": <STRING matching input srs_id>,
  "interpretation": "<Clear natural-language summary of the requirement's formal logic>",
  "identified_entities": [
    "<System component, processor, message, or signal name>"
  ],
  "predicates": [
    "<Boolean predicate or state expression, e.g. active(sensor), in_mode(state)>"
  ],
  "conditions": [
    "<Trigger or precondition statement>"
  ],
  "actions": [
    "<Action or postcondition statement>"
  ],
  "temporal_constraints": [
    "<Bounded time or sequence constraint, e.g. within T time units, after event E>"
  ],
  "mathematical_constraints": [
    "<Derived metric or threshold equation, e.g. metric > threshold>"
  ],
  "dependencies": [
    "<Prerequisite requirement SRS ID or component dependency>"
  ],
  "intermediate_representation": {
    "propositions": [
      {
        "symbol": "<Proposition symbol, e.g. P1, P_RESET, P_INIT>",
        "definition": "<Natural language statement or state, e.g. power-on reset occurs>",
        "notation": "<Explicit mathematical notation, e.g. P_RESET := power-on reset occurs>",
        "source_reference": "<Direct quote from SRS text>",
        "provenance": "EXPLICIT_SOURCE | SUPPORTED_DEPENDENCY | APPROVED_DERIVATION | UNRESOLVED | UNSUPPORTED"
      }
    ],
    "predicates": [
      {
        "name": "<Predicate name, e.g. perform_init_functions>",
        "entity": "<Entity name, e.g. System_Initialization>",
        "arguments": ["<arg1>", "<arg2>"],
        "condition_type": "TRIGGER | PRECONDITION | ACTION | POSTCONDITION | STATE",
        "description": "<Detailed description of predicate meaning>",
        "formal_expression": "<Optional lower-level expression, e.g. init_funcs_executed == true>",
        "notation": "<Formal notation, e.g. perform_init(sys) := System Initialization executes init functions>"
      }
    ],
    "entities": [
      {
        "name": "<System entity or component name>",
        "category": "ENTITY | VARIABLE | CONSTANT",
        "description": "<Role of this entity>"
      }
    ],
    "temporal_operators": [
      "<Temporal operators used, e.g. G, F, X>"
    ],
    "atomic_clauses": [
      "<List of all proposition and predicate notations>"
    ],
    "composition_rules": [
      "<Logical composition rule connecting propositions>"
    ],
    "formula_construction": "<Step-by-step explanation demonstrating how the final formula is constructed from the defined propositions and operators>",
    "unresolved_parameters": [
      "<Missing timing bounds or unstated parameters, e.g. t_bound>"
    ]
  },
  "formalization": "<Pure mathematical formula string composed from defined proposition symbols, e.g. G(P_RESET -> F P_INIT). NEVER embed ':=' or natural-language prose definitions here.>",
  "assumptions": [
    "<Explicit engineering assumptions made during formalization>"
  ],
  "unresolved_items": [
    "<Unstated parameters, missing bounds, or ambiguities requiring clarification>"
  ],
  "constraint_provenance": [
    {
      "constraint_id": "<e.g. C1, C2>",
      "statement": "<Constraint or parameter statement>",
      "category": "EXPLICIT_SOURCE | SUPPORTED_DEPENDENCY | APPROVED_DERIVATION | UNRESOLVED | UNSUPPORTED",
      "source_text": "<Quote from requirement text if applicable>",
      "justification": "<Source basis or dependency justification>"
    }
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

    # Format Answered Clarifications if present
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
        clarifs_str = "\n".join(clarifs_lines)
    else:
        clarifs_str = "No prior stakeholder clarifications."

    # Format Set-Level Context if present
    set_ctx = getattr(context_package, "set_context", None)
    if set_ctx:
        set_lines = []
        if "section_clusters" in set_ctx:
            set_lines.append(f"  - Related Section Requirements: {set_ctx.get('section_clusters', '')}")
        if "shared_entities" in set_ctx:
            set_lines.append(f"  - Set Shared Entities: {set_ctx.get('shared_entities', '')}")
        if "cross_dependencies" in set_ctx:
            set_lines.append(f"  - Identified Cross-Dependencies: {set_ctx.get('cross_dependencies', '')}")
        if "summary" in set_ctx:
            set_lines.append(f"  - Set Analysis Summary: {set_ctx.get('summary', '')}")
        set_str = "\n".join(set_lines) if set_lines else "None recorded."
    else:
        set_str = "Single-requirement analysis (no set-level batch context)."

    # Format Available Symbols from Symbol Registry
    symbols_list = getattr(context_package, "symbols", [])
    if symbols_list:
        sym_lines = []
        for s in symbols_list:
            if getattr(s, "is_active", True):
                sig = f"({s.signature})" if getattr(s, "signature", None) else ""
                desc = getattr(s, "definition", "")
                cat = getattr(s, "category", "")
                sc = getattr(s, "scope", "")
                sp = getattr(s, "spelling", "")
                sym_lines.append(f"  - {sp}{sig} [{cat}, scope: {sc}]: {desc}")
        symbols_str = "\n".join(sym_lines) if sym_lines else "None registered."
    else:
        symbols_str = "None registered."

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
4. STAKEHOLDER CLARIFICATION RESOLUTIONS
==========================================================
{clarifs_str}

==========================================================
5. SET-LEVEL CONTEXT & CROSS-REQUIREMENT DEPENDENCIES
==========================================================
{set_str}

==========================================================
6. CANONICAL & REGISTERED DOMAIN SYMBOLS
==========================================================
{symbols_str}

==========================================================
INSTRUCTIONS
==========================================================
1. Analyze the exact source requirement logic using raw text, retrieved Obsidian knowledge, and any set-level dependencies.
2. Identify entities, predicates, conditions, actions, temporal constraints, mathematical constraints, and dependencies.
3. Explicitly define all atomic propositions in "intermediate_representation.propositions" using mathematical notation P := <Natural Language Statement>. Distinguish capability statements from invocation events (do not collapse them).
4. Explicitly define predicates with arguments, condition types, and natural language descriptions under "intermediate_representation.predicates".
5. Show step-by-step "formula_construction" explaining how the candidate formalization is assembled directly from the defined propositions, predicates, and operators.
6. Construct the candidate formal mathematical logic statement under "formalization" using ONLY the declared propositions and predicates. Do not force temporal logic when an untimed capability contract is appropriate. NEVER write ":=" or natural-language prose definitions inside "formalization" (definitions belong exclusively in intermediate_representation).
7. Explicitly list any assumptions under "assumptions" and unstated/missing parameters under "unresolved_items" and "unresolved_parameters".
8. DO NOT invent timing bounds (e.g. t_bound) or artificial Until (U) operators when none is stated in the SRS text. If a bound is missing, mark it in "unresolved_items" and "unresolved_parameters" with provenance UNRESOLVED.
9. Incorporate all approved stakeholder clarification resolutions into the formalization.
10. Provide constraint provenance for each identified constraint classifying it as EXPLICIT_SOURCE, SUPPORTED_DEPENDENCY, APPROVED_DERIVATION, UNRESOLVED, or UNSUPPORTED.
11. Use registered domain symbols and canonical operators where applicable with exact spellings and definitions.
12. CRITICAL IDENTITY REQUIREMENT: Your output JSON MUST include the root fields "requirement_id": {req.requirement_id}, "global_number": {req.global_number}, and "srs_id": "{req.srs_id}".
13. Output a single valid JSON object matching the requested schema.
"""
