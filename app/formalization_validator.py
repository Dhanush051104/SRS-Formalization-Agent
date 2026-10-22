"""Deterministic structural checks for the project's LTL-style notation.

This validator is STRUCTURAL ONLY. A formula that passes has balanced
delimiters and every temporal / logical operator has an operand. It says
nothing about whether the formula correctly captures the requirement; that
remains the job of the critic and of human review.

The notation accepted matches the examples used by the reasoning prompt and
the knowledge notes, e.g.:

    G(failed_sync_2.5s -> F[0,1s] send_vme_reset)
    G(comm_lost -> F safe_state)
    G (p -> F (q))
    time_since_loss > 2.5s

Non-temporal formulas (metric constraints, predicate expressions) are valid
as long as they are non-empty and structurally balanced.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional

STRUCTURAL_ONLY_NOTE = (
    "Structural check only: it does not establish that the formula is semantically "
    "correct for the requirement."
)

_CONNECTIVE = r"(?:<->|->|&&|\|\|)"
# Unary temporal operator (G, F, X) as a standalone token, with an optional [a,b] bound.
_UNARY_TEMPORAL = re.compile(r"(?<![\w.])[GFX](?![\w.])(?:\s*\[[^\]]*\])?")
_CLOSERS = ")]},;"


@dataclass
class FormalizationValidationReport:
    is_valid: bool
    findings: List[dict] = field(default_factory=list)


def validate_formalization(expression: Optional[str]) -> FormalizationValidationReport:
    """Validate formula structure. Never raises; returns findings explaining each failure."""
    findings: List[dict] = []
    text = (expression or "").strip()
    if not text:
        findings.append(_finding("EMPTY_EXPRESSION", "Formalization is empty."))
        return FormalizationValidationReport(False, findings)

    delimiter_problem = _check_delimiters(text)
    if delimiter_problem:
        findings.append(_finding("UNBALANCED_DELIMITER", delimiter_problem))

    if ":=" in text:
        findings.append(_finding(
            "DEFINITION_EMBEDDED_IN_FORMULA",
            "Formalization contains definition syntax ':=' or embedded prose definition. "
            "Formulas must reference declared symbols without embedding definition text.",
            recommendation="Remove ':=' and definition prose from formalization. Reference only declared symbol names.",
        ))

    if _has_operandless_temporal_operator(text):
        findings.append(_finding(
            "INCOMPLETE_TEMPORAL_OPERATOR",
            "A temporal operator (G, F or X) has no operand, e.g. 'G(p -> F)'.",
        ))

    if (
        re.match(r"\s*" + _CONNECTIVE, text)
        or re.search(r"\(\s*" + _CONNECTIVE, text)
        or re.search(_CONNECTIVE + r"\s*(?:$|\))", text)
        or re.search(_CONNECTIVE + r"\s*" + _CONNECTIVE, text)
    ):
        findings.append(_finding(
            "MALFORMED_BINARY_OPERATOR",
            "A logical connective (->, <->, &&, ||) is missing an operand.",
        ))

    return FormalizationValidationReport(not findings, findings)


def _check_delimiters(text: str) -> Optional[str]:
    pairs = {")": "(", "]": "[", "}": "{"}
    stack: List[str] = []
    for char in text:
        if char in "([{":
            stack.append(char)
        elif char in pairs:
            if not stack or stack.pop() != pairs[char]:
                return "Formalization has an unmatched closing delimiter."
    if stack:
        return "Formalization has an unclosed delimiter."
    return None


def _has_operandless_temporal_operator(text: str) -> bool:
    for match in _UNARY_TEMPORAL.finditer(text):
        rest = text[match.end():].lstrip()
        if not rest or rest[0] in _CLOSERS or re.match(_CONNECTIVE, rest):
            return True
    return False


def _finding(rule: str, description: str, recommendation: Optional[str] = None) -> dict:
    return {
        "category": "FORMALIZATION_STRUCTURE",
        "severity": "ERROR",
        "rule": rule,
        "description": description,
        "recommendation": recommendation or "Revise the formula so every operator has a complete operand and delimiters balance.",
    }
