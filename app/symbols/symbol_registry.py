import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from app.symbols.schemas import (
    SymbolDefinition,
    SymbolRegistryError,
    SymbolValidationError,
)

DEFAULT_REGISTRY_PATH = Path("data") / "symbol_registry.json"


class SymbolRegistry:
    """
    Authoritative, canonical repository for mathematical, temporal, and domain symbols.
    Enforces deterministic validation rules preventing duplicate identifiers, conflicting
    definitions, and unauthorized silent symbol redefinitions.
    """

    def __init__(self, registry_path: Optional[Union[Path, str]] = None) -> None:
        """
        Initialize the SymbolRegistry.

        Args:
            registry_path: Path to symbol_registry.json. If None, resolves relative to project root.
        """
        if registry_path is None:
            project_root = Path(__file__).resolve().parent.parent.parent
            self.registry_path = project_root / DEFAULT_REGISTRY_PATH
        else:
            self.registry_path = Path(registry_path).resolve()

        self.version: str = "1.0.0"
        self.description: str = ""
        self._symbols_by_id: Dict[str, SymbolDefinition] = {}
        self._symbols_list: List[SymbolDefinition] = []

    def load(self) -> None:
        """
        Loads and validates the registry from disk.

        Raises:
            SymbolRegistryError: If the registry file is not found or contains malformed JSON.
            SymbolValidationError: If registry symbols violate uniqueness, scoping, or alias rules.
        """
        if not self.registry_path.exists():
            raise SymbolRegistryError(f"Symbol registry file not found at: {self.registry_path}")

        try:
            with open(self.registry_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            raise SymbolRegistryError(f"Failed to read or parse symbol registry JSON: {e}")

        if not isinstance(data, dict):
            raise SymbolRegistryError("Symbol registry JSON root must be an object/dictionary.")

        self.version = str(data.get("version", "1.0.0"))
        self.description = str(data.get("description", ""))

        raw_symbols = data.get("symbols", [])
        if not isinstance(raw_symbols, list):
            raise SymbolRegistryError("Field 'symbols' in symbol registry must be a list.")

        self.clear()

        # Parse and register each symbol with validation
        for idx, item in enumerate(raw_symbols):
            if not isinstance(item, dict):
                raise SymbolRegistryError(f"Symbol at index {idx} must be a dictionary.")
            symbol_def = SymbolDefinition.from_dict(item)
            self._validate_and_add(symbol_def)

    def clear(self) -> None:
        """Resets the in-memory registry to empty."""
        self._symbols_by_id.clear()
        self._symbols_list.clear()

    def _validate_and_add(self, symbol: SymbolDefinition) -> None:
        """
        Validates a symbol against existing registered symbols and adds it to indexes.

        Rules enforced:
        1. Unique identifier: Symbol identifier must be globally unique across registry.
        2. Scope conflict: Within the same scope, no two symbols can have the exact same spelling.
        3. Alias conflict: Within the same scope, no alias may collide with another symbol's spelling or alias.
        """
        # 1. Identifier uniqueness
        if symbol.identifier in self._symbols_by_id:
            raise SymbolValidationError(
                f"Duplicate symbol identifier '{symbol.identifier}' found in registry."
            )

        clean_scope = symbol.scope.strip().lower()
        symbol_spellings = {symbol.spelling.lower()} | {a.lower() for a in symbol.aliases}

        # 2. Check collision within the same scope
        for existing in self._symbols_list:
            existing_scope = existing.scope.strip().lower()

            # Check if scopes match or if one is global and one is requirement-specific
            same_scope = (clean_scope == existing_scope)

            if same_scope:
                existing_spellings = {existing.spelling.lower()} | {a.lower() for a in existing.aliases}
                overlap = symbol_spellings.intersection(existing_spellings)
                if overlap:
                    raise SymbolValidationError(
                        f"Spelling or alias conflict in scope '{symbol.scope}': {sorted(overlap)} "
                        f"between '{symbol.identifier}' and existing '{existing.identifier}'."
                    )

        self._symbols_by_id[symbol.identifier] = symbol
        self._symbols_list.append(symbol)

    def register_symbol(self, symbol: SymbolDefinition) -> None:
        """
        Programmatically registers a new symbol into the registry.
        Enforces all deterministic validation rules.

        Args:
            symbol: SymbolDefinition to register.

        Raises:
            SymbolValidationError: If symbol violates validation rules.
        """
        self._validate_and_add(symbol)

    def get_symbol_by_identifier(self, identifier: str) -> Optional[SymbolDefinition]:
        """Lookup a symbol by its unique identifier."""
        return self._symbols_by_id.get(identifier)

    def get_all_symbols(self) -> List[SymbolDefinition]:
        """Returns all registered symbols sorted deterministically by identifier."""
        return sorted(self._symbols_list, key=lambda s: s.identifier)

    def get_symbol_by_spelling(self, spelling: str, scope: Optional[str] = None) -> Optional[SymbolDefinition]:
        """
        Lookup a symbol by spelling, optionally matching scope.
        Prioritizes requirement-specific symbols in the given scope before falling back to global symbols.
        """
        target = spelling.strip().lower()
        clean_target_scope = scope.strip().lower().strip("[]") if scope else None

        scoped_match = None
        global_match = None

        for sym in self._symbols_list:
            sym_spellings = [sym.spelling.lower()] + [a.lower() for a in sym.aliases]
            if target in sym_spellings:
                if clean_target_scope:
                    sym_clean_scope = sym.scope.strip().lower().strip("[]")
                    if sym_clean_scope == clean_target_scope and not sym.is_global():
                        scoped_match = sym
                        break
                if sym.is_global() and global_match is None:
                    global_match = sym

        return scoped_match or global_match

    def search_symbols(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        scope: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[SymbolDefinition]:
        """
        Filters symbols deterministically by query text, category, scope, and active status.
        """
        results = self.get_all_symbols()

        if status:
            stat_clean = status.strip().lower()
            if stat_clean == "active":
                results = [s for s in results if s.is_active]
            elif stat_clean == "deactivated":
                results = [s for s in results if not s.is_active]

        if category:
            cat_clean = category.strip().upper()
            if cat_clean and cat_clean != "ALL":
                results = [s for s in results if s.category == cat_clean]

        if scope:
            sc_clean = scope.strip().lower()
            if sc_clean and sc_clean != "all":
                if sc_clean == "global":
                    results = [s for s in results if s.is_global()]
                else:
                    results = [s for s in results if s.matches_scope(scope)]

        if query:
            q_clean = query.strip().lower()
            if q_clean:
                matched = []
                for s in results:
                    text_blob = (
                        f"{s.identifier} {s.spelling} {s.definition} {' '.join(s.aliases)} "
                        f"{s.notes or ''} {s.signature or ''} {s.scope} {s.category}"
                    ).lower()
                    if q_clean in text_blob:
                        matched.append(s)
                results = matched

        return sorted(results, key=lambda s: (not s.is_active, s.identifier))

    def update_symbol_definition(
        self,
        identifier: str,
        new_definition: str,
        notes: Optional[str] = None,
        arity: Optional[int] = None,
        signature: Optional[str] = None,
        user_approved: bool = True,
    ) -> SymbolDefinition:
        """
        Updates a symbol's definition, signature, and notes, marking provenance as user-approved.
        Validates that new definition is non-empty.
        """
        sym = self.get_symbol_by_identifier(identifier)
        if not sym:
            raise SymbolValidationError(f"Symbol '{identifier}' does not exist in registry.")

        clean_def = new_definition.strip()
        if not clean_def:
            raise SymbolValidationError("Symbol definition cannot be empty.")

        sym.definition = clean_def
        if notes is not None:
            sym.notes = notes.strip() if notes.strip() else None
        if signature is not None:
            sym.signature = signature.strip() if signature.strip() else None
        if arity is not None:
            try:
                sym.arity = int(arity) if int(arity) >= 0 else None
            except (ValueError, TypeError):
                sym.arity = None

        if user_approved:
            sym.user_approved = True
            sym.provenance["user_approved"] = True
            sym.provenance["last_edited_by"] = "user"
            sym.provenance["last_edited_at"] = datetime.now(timezone.utc).isoformat()

        self.save()
        return sym

    def find_symbol_references(self, identifier_or_spelling: str) -> Dict[str, Any]:
        """
        Scans historical results (result_cache.json, history_store.json), other symbols,
        and database requirement scopes to detect all usage references of a symbol.
        """
        sym = self.get_symbol_by_identifier(identifier_or_spelling)
        if not sym:
            sym = self.get_symbol_by_spelling(identifier_or_spelling)

        if not sym:
            return {
                "identifier": identifier_or_spelling,
                "spelling": identifier_or_spelling,
                "found": False,
                "is_core_operator": False,
                "cache_references": [],
                "history_references": [],
                "scope_references": [],
                "total_references": 0,
                "can_permanently_delete": False,
                "can_deactivate": False,
                "delete_block_reason": f"Symbol '{identifier_or_spelling}' not found in registry.",
            }

        # Check core operators (foundational temporal operators and logical connectives)
        is_core_operator = sym.category in {"TEMPORAL_OPERATOR", "LOGICAL_CONNECTIVE"} and sym.is_global()

        tokens = {sym.spelling.lower()} | {a.lower() for a in sym.aliases} | {sym.identifier.lower()}

        def matches_tokens(text: str) -> bool:
            if not text:
                return False
            text_lower = text.lower()
            return any(tok in text_lower for tok in tokens)

        def matches_list(items: Any) -> bool:
            if not items or not isinstance(items, list):
                return False
            for item in items:
                if isinstance(item, str) and item.lower() in tokens:
                    return True
                elif isinstance(item, dict):
                    if (
                        item.get("identifier", "").lower() in tokens
                        or item.get("spelling", "").lower() in tokens
                        or item.get("name", "").lower() in tokens
                    ):
                        return True
            return False

        cache_refs: List[Dict[str, Any]] = []
        result_cache_file = self.registry_path.parent / "result_cache.json"
        if result_cache_file.exists():
            try:
                cache_data = json.loads(result_cache_file.read_text(encoding="utf-8"))
                if isinstance(cache_data, dict):
                    for k, val in cache_data.items():
                        res = val.get("result", {})
                        formalization = str(res.get("formalization", ""))
                        symbols = res.get("symbols", [])
                        predicates = res.get("predicates", [])
                        entities = res.get("identified_entities", [])
                        srs_id = str(res.get("srs_id", ""))
                        req_id = res.get("requirement_id")

                        matched = (
                            matches_tokens(formalization)
                            or matches_list(symbols)
                            or matches_list(predicates)
                            or matches_list(entities)
                        )
                        if matched:
                            cache_refs.append({
                                "requirement_id": req_id,
                                "srs_id": srs_id,
                                "formalization": formalization[:120],
                                "saved_at": val.get("saved_at", ""),
                            })
            except Exception:
                pass

        history_refs: List[Dict[str, Any]] = []
        history_file = self.registry_path.parent / "history_store.json"
        if history_file.exists():
            try:
                hist_data = json.loads(history_file.read_text(encoding="utf-8"))
                runs = hist_data.get("runs", []) if isinstance(hist_data, dict) else []
                for r in runs:
                    run_id = r.get("run_id", "")
                    for item in r.get("items", []):
                        formalization = str(item.get("formalization", ""))
                        predicates = item.get("predicates", [])
                        entities = item.get("identified_entities", [])
                        srs_id = str(item.get("srs_id", ""))
                        req_id = item.get("requirement_id")

                        matched = (
                            matches_tokens(formalization)
                            or matches_list(predicates)
                            or matches_list(entities)
                        )
                        if matched:
                            history_refs.append({
                                "run_id": run_id,
                                "requirement_id": req_id,
                                "srs_id": srs_id,
                                "formalization": formalization[:120],
                                "created_at": r.get("created_at", ""),
                            })
            except Exception:
                pass

        scope_refs: List[Dict[str, Any]] = []
        if not sym.is_global() and sym.scope:
            clean_scope = sym.scope.strip("[]").upper()
            scope_refs.append({
                "scope": sym.scope,
                "description": f"Scoped to requirement [{clean_scope}]",
            })

        total_refs = len(cache_refs) + len(history_refs)

        if is_core_operator:
            can_perm_delete = False
            can_deactivate = False
            block_reason = "Core temporal logic operators and propositional connectives are foundational to the formalization engine and cannot be modified, deactivated, or deleted."
        elif total_refs > 0:
            can_perm_delete = False
            can_deactivate = True
            block_reason = f"Symbol is referenced in {total_refs} past formalization results ({len(cache_refs)} in result cache, {len(history_refs)} in history ledger). Permanent deletion is blocked to preserve result integrity. You may deactivate this symbol instead."
        else:
            can_perm_delete = True
            can_deactivate = True
            block_reason = None

        return {
            "identifier": sym.identifier,
            "spelling": sym.spelling,
            "category": sym.category,
            "scope": sym.scope,
            "found": True,
            "is_core_operator": is_core_operator,
            "cache_references": cache_refs,
            "history_references": history_refs,
            "scope_references": scope_refs,
            "total_references": total_refs,
            "can_permanently_delete": can_perm_delete,
            "can_deactivate": can_deactivate,
            "delete_block_reason": block_reason,
        }

    def deactivate_symbol(self, identifier: str) -> SymbolDefinition:
        """
        Deactivates a symbol (soft delete). Prevents downstream use while protecting history.
        Core operators cannot be deactivated.
        """
        sym = self.get_symbol_by_identifier(identifier)
        if not sym:
            raise SymbolValidationError(f"Symbol '{identifier}' does not exist in registry.")

        if sym.category in {"TEMPORAL_OPERATOR", "LOGICAL_CONNECTIVE"} and sym.is_global():
            raise SymbolValidationError("Cannot deactivate core temporal logic operators or propositional connectives.")

        sym.is_active = False
        sym.provenance["deactivated_at"] = datetime.now(timezone.utc).isoformat()
        self.save()
        return sym

    def activate_symbol(self, identifier: str) -> SymbolDefinition:
        """
        Reactivates a previously deactivated symbol.
        """
        sym = self.get_symbol_by_identifier(identifier)
        if not sym:
            raise SymbolValidationError(f"Symbol '{identifier}' does not exist in registry.")

        sym.is_active = True
        sym.provenance.pop("deactivated_at", None)
        self.save()
        return sym

    def delete_symbol(self, identifier: str, force: bool = False) -> bool:
        """
        Permanently deletes a symbol if unreferenced. If referenced and force=False, raises SymbolValidationError.
        """
        sym = self.get_symbol_by_identifier(identifier)
        if not sym:
            raise SymbolValidationError(f"Symbol '{identifier}' does not exist in registry.")

        if sym.category in {"TEMPORAL_OPERATOR", "LOGICAL_CONNECTIVE"} and sym.is_global():
            raise SymbolValidationError("Cannot delete core temporal logic operators or propositional connectives.")

        refs = self.find_symbol_references(identifier)
        if refs["total_references"] > 0 and not force:
            raise SymbolValidationError(
                f"Cannot permanently delete '{identifier}': it is referenced in {refs['total_references']} "
                f"historical results. Consider deactivating it instead."
            )

        del self._symbols_by_id[identifier]
        self._symbols_list = [s for s in self._symbols_list if s.identifier != identifier]
        self.save()
        return True

    def register_domain_symbol(
        self,
        spelling: str,
        category: str,
        scope: str,
        definition: str,
        arity: Optional[int] = None,
        signature: Optional[str] = None,
        notes: Optional[str] = None,
        aliases: Optional[List[str]] = None,
        provenance: Optional[Dict[str, Any]] = None,
        user_approved: bool = False,
    ) -> Tuple[SymbolDefinition, bool]:
        """
        Registers a domain symbol (predicate, entity, proposition, etc.).
        Avoids duplicating existing symbols.
        If a symbol with matching spelling and scope exists:
          - If existing has user_approved=True and incoming has user_approved=False, preserves existing!
          - Returns (existing_symbol, False)
        If not existing:
          - Creates and registers new symbol, returns (new_symbol, True)
        """
        clean_spelling = spelling.strip()
        clean_scope = scope.strip()
        cat_clean = category.strip().upper()

        # Check existing by spelling and scope
        existing = self.get_symbol_by_spelling(clean_spelling, scope=clean_scope)
        if existing:
            # If user previously approved this symbol, never overwrite it with an automated model proposition
            if existing.user_approved and not user_approved:
                return existing, False
            # If incoming is user_approved, or existing is not user approved, update definition if given
            if definition and definition.strip():
                existing.definition = definition.strip()
            if notes:
                existing.notes = notes.strip()
            if arity is not None:
                existing.arity = arity
            if signature:
                existing.signature = signature.strip()
            if user_approved:
                existing.user_approved = True
                existing.provenance["user_approved"] = True
                existing.provenance["last_edited_by"] = "user"
                existing.provenance["last_edited_at"] = datetime.now(timezone.utc).isoformat()
            self.save()
            return existing, False

        # Generate unique identifier
        safe_scope = clean_scope.strip("[]").lower().replace(" ", "_").replace("-", "_")
        safe_spelling = "".join(c if c.isalnum() or c == "_" else "_" for c in clean_spelling.lower()).strip("_")
        base_id = f"sym_{safe_scope}_{safe_spelling}" if safe_scope else f"sym_{safe_spelling}"
        ident = base_id
        counter = 1
        while ident in self._symbols_by_id:
            ident = f"{base_id}_{counter}"
            counter += 1

        prov = dict(provenance or {})
        if user_approved:
            prov["user_approved"] = True
            prov["created_by"] = "user"
            prov["created_at"] = datetime.now(timezone.utc).isoformat()

        new_sym = SymbolDefinition(
            identifier=ident,
            spelling=clean_spelling,
            definition=definition.strip(),
            category=cat_clean,
            scope=clean_scope,
            provenance=prov,
            aliases=list(aliases or []),
            notes=notes.strip() if notes else None,
            arity=arity,
            signature=signature.strip() if signature else None,
            is_active=True,
            user_approved=user_approved,
        )

        self.register_symbol(new_sym)
        self.save()
        return new_sym, True

    def __len__(self) -> int:
        return len(self._symbols_list)

    def save(self, target_path: Optional[Union[Path, str]] = None) -> None:
        """
        Serializes and saves the registry to disk.

        Args:
            target_path: Optional output path. If None, saves to self.registry_path.
        """
        out_path = Path(target_path).resolve() if target_path else self.registry_path
        payload = {
            "version": self.version,
            "description": self.description,
            "symbols": [s.to_dict() for s in self.get_all_symbols()],
        }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
