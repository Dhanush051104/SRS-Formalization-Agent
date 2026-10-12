import json
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
