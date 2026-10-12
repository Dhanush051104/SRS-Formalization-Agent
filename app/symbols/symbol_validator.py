import re
from typing import Any, Dict, List, Optional, Set

from app.symbols.schemas import (
    SymbolDefinition,
    SymbolValidationReport,
    SymbolViolation,
)
from app.symbols.symbol_registry import SymbolRegistry


class SymbolValidator:
    """
    Deterministic consistency validator for candidate mathematical formalizations.

    Validates candidate formalization strings, predicates, and entities against the canonical
    SymbolRegistry. Detects out-of-scope symbol usage, conflicting definitions, and unregistered
    symbols.

    VALIDATOR LIMITATIONS & SCOPE:
    1. Lexical Tokenization: This validator relies on deterministic regex and token extraction.
       It does NOT build a complete Abstract Syntax Tree (AST) for higher-order logics or custom grammars.
    2. Context Sensitivity: Symbols with overloaded mathematical meanings (e.g., single-letter variables)
       may produce false-positive unregistered notices in complex mathematical contexts.
    3. Advisory Notifications: Unregistered domain predicates are reported as advisory warnings or info
       to notify engineers, without claiming that LLM-proposed symbols are inherently erroneous.
    """

    def __init__(self, registry: SymbolRegistry) -> None:
        """
        Initialize the SymbolValidator with an authoritative SymbolRegistry.

        Args:
            registry: Instantiated and loaded SymbolRegistry.
        """
        self.registry = registry

    def _extract_tokens(self, text: str) -> Set[str]:
        """
        Extracts candidate lexical tokens from formalization text.
        Splits on common punctuation and whitespace, preserving identifiers and operators.
        """
        if not text or not text.strip():
            return set()

        # Extract words/identifiers (e.g. loss_of_comm, outputs_disabled, 10ms, G, F)
        word_tokens = set(re.findall(r"\b[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)?\b", text))

        # Also extract logic operators if present
        operators = set(re.findall(r"(?:->|<->|&&|\|\||!|\[\]|<>)", text))

        return word_tokens | operators

    def validate_candidate(
        self,
        formalization: str,
        predicates: Optional[List[str]] = None,
        entities: Optional[List[str]] = None,
        current_scope: Optional[str] = None,
        candidate_definitions: Optional[Dict[str, str]] = None,
    ) -> SymbolValidationReport:
        """
        Rigorously validates candidate formalization against canonical SymbolRegistry rules.

        Args:
            formalization: Mathematical or temporal formalization text (e.g., LTL formula).
            predicates: Optional list of identified predicates from reasoning result.
            entities: Optional list of identified entities from reasoning result.
            current_scope: The requirement scope under analysis (e.g., '[SRS178]').
            candidate_definitions: Optional mapping of symbol -> candidate definition string.

        Returns:
            SymbolValidationReport detailing violations and findings.
        """
        violations: List[SymbolViolation] = []
        tokens_in_text = self._extract_tokens(formalization)

        # Include predicates and entities
        all_candidate_tokens = set(tokens_in_text)
        if predicates:
            for p in predicates:
                all_candidate_tokens.update(self._extract_tokens(p))
        if entities:
            for e in entities:
                all_candidate_tokens.update(self._extract_tokens(e))

        checked_tokens = sorted(list(all_candidate_tokens))
        clean_current_scope = current_scope.strip().lower().strip("[]") if current_scope else None

        # Build index of registered spellings across registry
        # Maps spelling.lower() -> list of SymbolDefinitions
        spelling_map: Dict[str, List[SymbolDefinition]] = {}
        for sym in self.registry.get_all_symbols():
            for spell in [sym.spelling] + sym.aliases:
                spelling_map.setdefault(spell.lower(), []).append(sym)

        # 1. Check for Out-of-Scope Symbol Reuse
        for token in checked_tokens:
            token_lower = token.lower()
            if token_lower in spelling_map:
                matching_defs = spelling_map[token_lower]
                for sym_def in matching_defs:
                    if not sym_def.is_global():
                        # Requirement-specific symbol: must match current_scope
                        sym_clean_scope = sym_def.scope.strip().lower().strip("[]")
                        if clean_current_scope is None or sym_clean_scope != clean_current_scope:
                            violations.append(
                                SymbolViolation(
                                    rule="OUT_OF_SCOPE_SYMBOL",
                                    symbol_spelling=token,
                                    description=(
                                        f"Symbol '{token}' is registered specifically for scope '{sym_def.scope}' "
                                        f"but was referenced in scope '{current_scope or 'global'}' without explicit redeclaration."
                                    ),
                                    severity="ERROR",
                                    provenance=sym_def.provenance,
                                )
                            )

        # 2. Check for Conflicting Definitions in Candidate Result
        if candidate_definitions:
            for sym_key, cand_def in candidate_definitions.items():
                sym_key_lower = sym_key.strip().lower()
                if sym_key_lower in spelling_map:
                    matching_defs = spelling_map[sym_key_lower]
                    for sym_def in matching_defs:
                        # Check if applicable in this scope
                        if sym_def.is_global() or (clean_current_scope and sym_def.matches_scope(clean_current_scope)):
                            # Check whether candidate definition contradicts canonical definition
                            canon_def = sym_def.definition.lower()
                            user_def = cand_def.strip().lower()
                            # Heuristic contradiction check: if candidate definition shares zero key conceptual words
                            # or explicitly changes category/meaning
                            words_canon = set(re.findall(r"\w{4,}", canon_def))
                            words_user = set(re.findall(r"\w{4,}", user_def))
                            if words_canon and words_user and not (words_canon & words_user):
                                violations.append(
                                    SymbolViolation(
                                        rule="CONFLICTING_DEFINITION",
                                        symbol_spelling=sym_key,
                                        description=(
                                            f"Candidate definition '{cand_def}' for symbol '{sym_key}' conflicts "
                                            f"with canonical registered definition: '{sym_def.definition}'."
                                        ),
                                        severity="ERROR",
                                        provenance=sym_def.provenance,
                                    )
                                )

        # 3. Detect Unregistered Symbols where detectable
        # Filter out common punctuation, purely numeric literals, or standard keywords
        common_literals = {"0", "1", "true", "false", "and", "or", "not", "if", "then", "in"}
        for token in checked_tokens:
            token_lower = token.lower()
            if token_lower in common_literals or token.isdigit():
                continue
            if token_lower not in spelling_map:
                # If it looks like a formal domain identifier (contains underscore, or length > 2)
                if "_" in token or (len(token) > 2 and token.isalnum()):
                    violations.append(
                        SymbolViolation(
                            rule="UNREGISTERED_SYMBOL",
                            symbol_spelling=token,
                            description=f"Token '{token}' is not registered in the canonical SymbolRegistry.",
                            severity="INFO",
                            provenance={"source": "SymbolValidator", "scope": current_scope},
                        )
                    )

        # Determine overall validity (ERROR violations invalidate candidate)
        has_errors = any(v.severity == "ERROR" for v in violations)
        summary = (
            f"Symbol validation completed for scope '{current_scope or 'global'}'. "
            f"Checked {len(checked_tokens)} tokens. "
            f"Found {len(violations)} issues ({sum(1 for v in violations if v.severity == 'ERROR')} errors)."
        )

        return SymbolValidationReport(
            is_valid=(not has_errors),
            violations=violations,
            checked_symbols=checked_tokens,
            target_scope=current_scope,
            summary=summary,
        )
