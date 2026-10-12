from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from app.symbols.schemas import (
    SymbolDefinition,
    SymbolRetrievalError,
    SymbolRetrievalResult,
)
from app.symbols.symbol_registry import SymbolRegistry


class SymbolRetriever:
    """
    Deterministic retriever for mathematical, temporal, and domain symbols.
    Provides query interfaces for global symbols, requirement-specific symbols,
    category queries, and identifier/alias lookups while preserving provenance.
    """

    def __init__(self, registry: Optional[SymbolRegistry] = None) -> None:
        """
        Initialize the SymbolRetriever.

        Args:
            registry: Optional pre-loaded SymbolRegistry instance.
                      If None, instantiates and loads the default registry from disk.
        """
        if registry is None:
            self.registry = SymbolRegistry()
            self.registry.load()
        else:
            self.registry = registry

    def _provenance_meta(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        prov: Dict[str, Any] = {
            "source": "SymbolRegistry",
            "registry_path": str(self.registry.registry_path),
            "registry_version": self.registry.version,
        }
        if extra:
            prov.update(extra)
        return prov

    def get_global_symbols(self) -> SymbolRetrievalResult:
        """
        Retrieves all globally applicable symbols (e.g., standard temporal logic operators,
        propositional connectives).

        Returns:
            SymbolRetrievalResult containing deterministically sorted global symbols.
        """
        matches = [s for s in self.registry.get_all_symbols() if s.is_global()]
        return SymbolRetrievalResult(
            symbols=sorted(matches, key=lambda s: s.identifier),
            query_type="global",
            query_parameter="global",
            provenance=self._provenance_meta({"count": len(matches)}),
        )

    def get_symbols_for_requirement(self, requirement_id_or_srs: Union[str, int]) -> SymbolRetrievalResult:
        """
        Retrieves all symbols relevant to a specific requirement, combining global symbols
        and requirement-scoped symbols matching the requirement identifier.

        Args:
            requirement_id_or_srs: SRS tag (e.g., '[SRS178]', 'SRS178') or integer requirement ID.

        Returns:
            SymbolRetrievalResult containing global and requirement-specific symbols.
        """
        target_str = str(requirement_id_or_srs).strip()
        clean_tag = target_str.strip("[]").lower()

        matches: List[SymbolDefinition] = []
        for sym in self.registry.get_all_symbols():
            if sym.is_global():
                matches.append(sym)
            else:
                sym_clean_scope = sym.scope.strip("[]").lower()
                if (
                    sym_clean_scope == clean_tag
                    or sym_clean_scope == f"requirement:{clean_tag}"
                    or sym.provenance.get("srs_id", "").strip("[]").lower() == clean_tag
                    or str(sym.provenance.get("requirement_id", "")).strip() == clean_tag
                ):
                    matches.append(sym)

        return SymbolRetrievalResult(
            symbols=sorted(matches, key=lambda s: (not s.is_global(), s.identifier)),
            query_type="requirement",
            query_parameter=target_str,
            provenance=self._provenance_meta({"requirement_query": target_str, "count": len(matches)}),
        )

    def get_symbols_by_category(
        self,
        category: str,
        scope: Optional[str] = None,
    ) -> SymbolRetrievalResult:
        """
        Retrieves symbols belonging to a specific category (e.g., TEMPORAL_OPERATOR).

        Args:
            category: Symbol category string.
            scope: Optional scope filter. If provided, returns global symbols and
                   symbols matching the specified scope.

        Returns:
            SymbolRetrievalResult with matching symbols.
        """
        cat_clean = category.strip().upper()
        matches: List[SymbolDefinition] = []

        for sym in self.registry.get_all_symbols():
            if sym.category == cat_clean:
                if scope is None or sym.matches_scope(scope):
                    matches.append(sym)

        return SymbolRetrievalResult(
            symbols=sorted(matches, key=lambda s: s.identifier),
            query_type="category",
            query_parameter={"category": cat_clean, "scope": scope},
            provenance=self._provenance_meta({"category": cat_clean, "count": len(matches)}),
        )

    def get_symbol_by_identifier(self, identifier: str) -> Optional[SymbolDefinition]:
        """
        Looks up a symbol definition by its unique identifier.

        Args:
            identifier: Unique symbol identifier.

        Returns:
            SymbolDefinition or None.
        """
        return self.registry.get_symbol_by_identifier(identifier)

    def get_symbol_by_spelling_or_alias(
        self,
        spelling: str,
        scope: Optional[str] = None,
    ) -> Optional[SymbolDefinition]:
        """
        Looks up a symbol definition by its exact spelling or registered alias.
        Prioritizes requirement-specific symbols in the given scope before falling back to global symbols.

        Args:
            spelling: Symbol spelling or alias.
            scope: Optional requirement scope.

        Returns:
            Matching SymbolDefinition or None.
        """
        target = spelling.strip()
        target_lower = target.lower()

        scoped_match: Optional[SymbolDefinition] = None
        global_match: Optional[SymbolDefinition] = None

        for sym in self.registry.get_all_symbols():
            sym_spellings = [sym.spelling.lower()] + [a.lower() for a in sym.aliases]
            if target_lower in sym_spellings:
                if scope and sym.matches_scope(scope) and not sym.is_global():
                    scoped_match = sym
                    break
                elif sym.is_global() and global_match is None:
                    global_match = sym

        return scoped_match or global_match
