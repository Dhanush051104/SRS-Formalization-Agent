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
        intermediate_representation: Optional[Any] = None,
        identified_patterns: Optional[List[str]] = None,
        source_text: Optional[str] = None,
    ) -> SymbolValidationReport:
        """
        Rigorously validates candidate formalization against canonical SymbolRegistry rules.

        Args:
            formalization: Mathematical or temporal formalization text (e.g., LTL formula).
            predicates: Optional list of identified predicates from reasoning result.
            entities: Optional list of identified entities from reasoning result.
            current_scope: The requirement scope under analysis (e.g., '[SRS178]').
            candidate_definitions: Optional mapping of symbol -> candidate definition string.
            intermediate_representation: Optional IntermediateRepresentation dataclass or dict.

        Returns:
            SymbolValidationReport detailing violations and findings.
        """
        violations: List[SymbolViolation] = []
        has_embedded_definition = bool(formalization and ":=" in formalization)
        if has_embedded_definition:
            violations.append(
                SymbolViolation(
                    rule="DEFINITION_EMBEDDED_IN_FORMULA",
                    symbol_spelling=":=",
                    description=(
                        "Candidate formalization embeds definition statement ':=' and natural-language "
                        "definition prose instead of referencing declared symbol names."
                    ),
                    severity="ERROR",
                    provenance={"source": "SymbolValidator", "scope": current_scope},
                )
            )
            # Extract formula tokens only from before ':=' to prevent natural-language prose
            # from generating spurious undefined symbol errors while flagging the malformed formula.
            formula_part = formalization.split(":=")[0]
            tokens_in_text = self._extract_tokens(formula_part)
        else:
            tokens_in_text = self._extract_tokens(formalization)

        # Parse intermediate representation if provided
        ir_data: Optional[Dict[str, Any]] = None
        if intermediate_representation is not None:
            if hasattr(intermediate_representation, "to_dict"):
                ir_data = intermediate_representation.to_dict()
            elif isinstance(intermediate_representation, dict):
                ir_data = intermediate_representation

        local_props: Set[str] = set()
        local_preds: Set[str] = set()
        local_entities: Set[str] = set()
        local_unresolved: Set[str] = set()

        if ir_data:
            for p in ir_data.get("propositions", []):
                sym = p.get("symbol") if isinstance(p, dict) else getattr(p, "symbol", None)
                defn = p.get("definition") if isinstance(p, dict) else getattr(p, "definition", None)
                notat = p.get("notation") if isinstance(p, dict) else getattr(p, "notation", None)
                if sym and str(sym).strip() and (defn or notat):
                    local_props.add(str(sym).strip())
            for ac in ir_data.get("atomic_clauses", []):
                if isinstance(ac, str) and ":=" in ac:
                    sym = ac.split(":=", 1)[0].strip()
                    if sym:
                        local_props.add(sym)
            for pred in ir_data.get("predicates", []):
                pname = pred.get("name") if isinstance(pred, dict) else getattr(pred, "name", None)
                pdesc = pred.get("description") if isinstance(pred, dict) else getattr(pred, "description", None)
                pnotat = pred.get("notation") if isinstance(pred, dict) else getattr(pred, "notation", None)
                pexpr = pred.get("formal_expression") if isinstance(pred, dict) else getattr(pred, "formal_expression", None)
                pargs = pred.get("arguments") if isinstance(pred, dict) else getattr(pred, "arguments", [])
                pentity = pred.get("entity") if isinstance(pred, dict) else getattr(pred, "entity", None)
                if pname and str(pname).strip() and (pdesc or pnotat or pexpr):
                    local_preds.add(str(pname).strip())
                    if pargs and isinstance(pargs, list):
                        for arg in pargs:
                            if arg and str(arg).strip():
                                local_preds.add(str(arg).strip())
                    if pentity and str(pentity).strip():
                        local_entities.add(str(pentity).strip())
            for ent in ir_data.get("entities", []):
                ename = ent.get("name") if isinstance(ent, dict) else (ent if isinstance(ent, str) else getattr(ent, "name", None))
                if ename and str(ename).strip():
                    local_entities.add(str(ename).strip())
            for u in ir_data.get("unresolved_parameters", []):
                if u and str(u).strip():
                    local_unresolved.add(str(u).strip())

        # Include predicates and entities
        all_candidate_tokens = set(tokens_in_text)
        if ir_data is None:
            if predicates:
                for p in predicates:
                    all_candidate_tokens.update(self._extract_tokens(p))
            if entities:
                for e in entities:
                    all_candidate_tokens.update(self._extract_tokens(e))
        if local_props:
            all_candidate_tokens.update(local_props)
        if local_preds:
            all_candidate_tokens.update(local_preds)
        if local_entities:
            all_candidate_tokens.update(local_entities)

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
                has_global = any(s.is_global() for s in matching_defs)
                has_in_scope = any(
                    clean_current_scope and s.scope.strip().lower().strip("[]") == clean_current_scope
                    for s in matching_defs
                )
                if not has_global and not has_in_scope:
                    # Token is registered ONLY in other scopes
                    out_of_scope_scopes = [s.scope for s in matching_defs]
                    violations.append(
                        SymbolViolation(
                            rule="OUT_OF_SCOPE_SYMBOL",
                            symbol_spelling=token,
                            description=(
                                f"Symbol '{token}' is registered specifically for scope(s) {out_of_scope_scopes} "
                                f"but was referenced in scope '{current_scope or 'global'}' without explicit redeclaration."
                            ),
                            severity="ERROR",
                            provenance=matching_defs[0].provenance,
                        )
                    )

        # 2. Check for Conflicting Definitions in Candidate Result
        merged_definitions: Dict[str, str] = dict(candidate_definitions or {})
        if ir_data:
            for p in ir_data.get("propositions", []):
                sym = p.get("symbol") if isinstance(p, dict) else getattr(p, "symbol", None)
                defn = p.get("definition") if isinstance(p, dict) else getattr(p, "definition", None)
                if sym and defn and str(sym).strip() not in merged_definitions:
                    merged_definitions[str(sym).strip()] = str(defn).strip()
            for pred in ir_data.get("predicates", []):
                pname = pred.get("name") if isinstance(pred, dict) else getattr(pred, "name", None)
                pdesc = pred.get("description") if isinstance(pred, dict) else getattr(pred, "description", None)
                if pname and pdesc and str(pname).strip() not in merged_definitions:
                    merged_definitions[str(pname).strip()] = str(pdesc).strip()

        if merged_definitions:
            for sym_key, cand_def in merged_definitions.items():
                sym_key_lower = sym_key.strip().lower()
                if sym_key_lower in spelling_map:
                    matching_defs = spelling_map[sym_key_lower]
                    for sym_def in matching_defs:
                        # Check if applicable in this scope
                        if sym_def.is_global() or (clean_current_scope and sym_def.matches_scope(clean_current_scope)):
                            # Check whether candidate definition contradicts canonical definition
                            canon_def = sym_def.definition.lower()
                            user_def = cand_def.strip().lower()
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

        # 3. Explicit Proposition Grounding & Undefined Formula Symbols (when IR is provided)
        standard_math_tokens = {
            "G", "F", "X", "U", "R", "W", "M", "->", "<->", "&&", "||", "!", "[]", "<>",
            "&", "|", "~", "==", "!=", "<=", ">=", "<", ">", "+", "-", "*", "/",
            "0", "1", "true", "false", "and", "or", "not", "if", "then", "in",
            "t", "s", "ms", "sec", "min", "hr", "us", "ns"
        }
        known_local_symbols = {s.lower() for s in (local_props | local_preds | local_entities | local_unresolved | set(merged_definitions.keys()))}
        if ir_data is None:
            # Fallback for legacy calls without IntermediateRepresentation:
            if predicates:
                for p in predicates:
                    known_local_symbols.update(t.lower() for t in self._extract_tokens(p))
            if entities:
                for e in entities:
                    known_local_symbols.update(t.lower() for t in self._extract_tokens(e))

        if ir_data is not None:
            # Check for unjustified temporal operator 'U' (Until)
            if "U" in tokens_in_text:
                temp_ops = [str(op).upper() for op in ir_data.get("temporal_operators", [])]
                has_until_pattern = False
                if identified_patterns:
                    until_pattern_keywords = {"until", "waiting", "persistence", "holding"}
                    for pat in identified_patterns:
                        if any(kw in pat.lower() for kw in until_pattern_keywords):
                            has_until_pattern = True
                            break
                has_until_text = bool(source_text and re.search(r"\b(until|unless)\b", source_text, re.IGNORECASE))

                is_unjustified = False
                if "U" not in temp_ops and "UNTIL" not in temp_ops:
                    is_unjustified = True
                elif (identified_patterns or source_text) and not has_until_pattern and not has_until_text:
                    is_unjustified = True

                if is_unjustified:
                    violations.append(
                        SymbolViolation(
                            rule="UNJUSTIFIED_TEMPORAL_OPERATOR",
                            symbol_spelling="U",
                            description=(
                                "Temporal operator 'U' (Until) is used in candidate formula but is not supported "
                                "by the source requirement text or identified structural patterns."
                            ),
                            severity="ERROR",
                            provenance={"source": "SymbolValidator", "scope": current_scope},
                        )
                    )

            # Check that formula references declared propositions or predicates
            if local_props or local_preds:
                token_lower_set = {t.lower() for t in tokens_in_text}
                referenced_props = {p for p in local_props if p.lower() in token_lower_set}
                referenced_preds = {p for p in local_preds if p.lower() in token_lower_set}
                if not referenced_props and not referenced_preds:
                    violations.append(
                        SymbolViolation(
                            rule="FORMULA_IR_DISCONNECTED",
                            symbol_spelling=formalization,
                            description=(
                                "Candidate formalization does not reference any of the declared propositions "
                                "or predicates defined in the intermediate representation."
                            ),
                            severity="ERROR",
                            provenance={"source": "SymbolValidator", "scope": current_scope},
                        )
                    )
            elif formalization:
                violations.append(
                    SymbolViolation(
                        rule="INSUFFICIENT_INTERMEDIATE_REPRESENTATION",
                        symbol_spelling=formalization,
                        description=(
                            "Candidate formalization was provided without any proposition or predicate "
                            "definitions in the intermediate representation."
                        ),
                        severity="ERROR",
                        provenance={"source": "SymbolValidator", "scope": current_scope},
                    )
                )

            for token in tokens_in_text:
                if token in standard_math_tokens or token.isdigit() or re.match(r"^\d+(?:ms|s|sec|min|hr|us|ns)?$", token):
                    continue
                token_lower = token.lower()
                is_in_registry = False
                if token_lower in spelling_map:
                    matching_defs = spelling_map[token_lower]
                    if any(s.is_global() or (clean_current_scope and s.matches_scope(clean_current_scope)) for s in matching_defs):
                        is_in_registry = True

                # Check if it's an unstated bound token (e.g. t_bound)
                if token_lower in {"t_bound", "t_max", "timeout", "t_limit", "t_response"}:
                    if token_lower not in known_local_symbols:
                        violations.append(
                            SymbolViolation(
                                rule="UNSTATED_TIMING_BOUND",
                                symbol_spelling=token,
                                description=(
                                    f"Timing parameter '{token}' is used in candidate formalization without explicit "
                                    f"source definition or categorization under unresolved_parameters."
                                ),
                                severity="ERROR",
                                provenance={"source": "SymbolValidator", "scope": current_scope},
                            )
                        )
                        continue

                if not is_in_registry and token_lower not in known_local_symbols:
                    violations.append(
                        SymbolViolation(
                            rule="UNDEFINED_FORMULA_SYMBOL",
                            symbol_spelling=token,
                            description=(
                                f"Formula token '{token}' is used in candidate formalization but has no explicit "
                                f"proposition or predicate definition in the intermediate representation."
                            ),
                            severity="ERROR",
                            provenance={"source": "SymbolValidator", "scope": current_scope},
                        )
                    )

        # 4. Detect Unregistered Symbols where detectable (Advisory INFO)
        common_literals = {"0", "1", "true", "false", "and", "or", "not", "if", "then", "in"}
        for token in checked_tokens:
            token_lower = token.lower()
            if token_lower in common_literals or token.isdigit():
                continue
            if token_lower not in spelling_map and token_lower not in known_local_symbols:
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
