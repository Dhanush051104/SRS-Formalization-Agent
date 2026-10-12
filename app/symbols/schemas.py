import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set

VALID_SYMBOL_CATEGORIES: Set[str] = {
    "TEMPORAL_OPERATOR",
    "LOGICAL_CONNECTIVE",
    "PREDICATE",
    "VARIABLE",
    "CONSTANT",
    "ACTION",
}

VALID_SEVERITIES: Set[str] = {"ERROR", "WARNING", "INFO"}


class SymbolError(Exception):
    """Base exception for all symbol registry and retrieval errors."""
    pass


class SymbolRegistryError(SymbolError):
    """Raised when loading, parsing, or configuring the symbol registry fails."""
    pass


class SymbolValidationError(SymbolError):
    """Raised when symbol definitions or candidate formalizations violate registry rules."""
    pass


class SymbolRetrievalError(SymbolError):
    """Raised when a symbol retrieval operation fails."""
    pass


@dataclass
class SymbolDefinition:
    """
    Canonical definition of a mathematical, temporal, or domain symbol.
    """
    identifier: str
    spelling: str
    definition: str
    category: str
    scope: str
    provenance: Dict[str, Any] = field(default_factory=dict)
    version: str = "1.0.0"
    aliases: List[str] = field(default_factory=list)
    notes: Optional[str] = None

    def is_global(self) -> bool:
        """Returns True if the symbol has global applicability."""
        return self.scope.strip().lower() == "global"

    def matches_scope(self, scope_query: str) -> bool:
        """
        Checks whether the symbol is applicable to the queried scope.
        Global symbols match all scopes. Requirement-specific symbols match if scope tags match.
        """
        if self.is_global():
            return True
        clean_target = scope_query.strip().lower().strip("[]")
        clean_own = self.scope.strip().lower().strip("[]")
        return clean_target == clean_own

    def to_dict(self) -> Dict[str, Any]:
        """Convert the SymbolDefinition to a dictionary."""
        return {
            "identifier": self.identifier,
            "spelling": self.spelling,
            "definition": self.definition,
            "category": self.category,
            "scope": self.scope,
            "provenance": dict(self.provenance),
            "version": self.version,
            "aliases": list(self.aliases),
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SymbolDefinition":
        """Construct a SymbolDefinition from a dictionary."""
        required = ["identifier", "spelling", "definition", "category", "scope"]
        missing = [f for f in required if f not in data or not str(data[f]).strip()]
        if missing:
            raise SymbolValidationError(f"Symbol definition missing required fields: {missing}")

        cat = str(data["category"]).strip().upper()
        if cat not in VALID_SYMBOL_CATEGORIES:
            raise SymbolValidationError(
                f"Invalid symbol category '{cat}'. Valid categories: {sorted(VALID_SYMBOL_CATEGORIES)}"
            )

        aliases_raw = data.get("aliases", [])
        if not isinstance(aliases_raw, list):
            raise SymbolValidationError("Field 'aliases' must be a list of strings.")

        return cls(
            identifier=str(data["identifier"]).strip(),
            spelling=str(data["spelling"]).strip(),
            definition=str(data["definition"]).strip(),
            category=cat,
            scope=str(data["scope"]).strip(),
            provenance=dict(data.get("provenance", {})),
            version=str(data.get("version", "1.0.0")).strip(),
            aliases=[str(a).strip() for a in aliases_raw],
            notes=data.get("notes"),
        )


@dataclass
class SymbolRetrievalResult:
    """
    Structured outcome of a symbol retrieval query, retaining provenance and deterministic ordering.
    """
    symbols: List[SymbolDefinition]
    query_type: str
    query_parameter: Any
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert SymbolRetrievalResult to a dictionary."""
        return {
            "symbols": [s.to_dict() for s in self.symbols],
            "query_type": self.query_type,
            "query_parameter": self.query_parameter,
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SymbolRetrievalResult":
        """Construct a SymbolRetrievalResult from a dictionary."""
        raw_symbols = data.get("symbols", [])
        return cls(
            symbols=[SymbolDefinition.from_dict(s) for s in raw_symbols],
            query_type=str(data.get("query_type", "unknown")),
            query_parameter=data.get("query_parameter"),
            provenance=dict(data.get("provenance", {})),
        )


@dataclass
class SymbolViolation:
    """
    Detailed report of a symbol consistency or scope violation.
    """
    rule: str
    symbol_spelling: str
    description: str
    severity: str = "ERROR"
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert SymbolViolation to a dictionary."""
        return {
            "rule": self.rule,
            "symbol_spelling": self.symbol_spelling,
            "description": self.description,
            "severity": self.severity,
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SymbolViolation":
        """Construct SymbolViolation from a dictionary."""
        sev = str(data.get("severity", "ERROR")).upper()
        if sev not in VALID_SEVERITIES:
            sev = "ERROR"
        return cls(
            rule=str(data.get("rule", "UNKNOWN_RULE")),
            symbol_spelling=str(data.get("symbol_spelling", "")),
            description=str(data.get("description", "")),
            severity=sev,
            provenance=dict(data.get("provenance", {})),
        )


@dataclass
class SymbolValidationReport:
    """
    Complete validation report evaluating candidate formalization symbols against canonical definitions.
    """
    is_valid: bool
    violations: List[SymbolViolation]
    checked_symbols: List[str]
    target_scope: Optional[str] = None
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert SymbolValidationReport to a dictionary."""
        return {
            "is_valid": self.is_valid,
            "violations": [v.to_dict() for v in self.violations],
            "checked_symbols": self.checked_symbols,
            "target_scope": self.target_scope,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SymbolValidationReport":
        """Construct SymbolValidationReport from a dictionary."""
        raw_violations = data.get("violations", [])
        return cls(
            is_valid=bool(data.get("is_valid", True)),
            violations=[SymbolViolation.from_dict(v) for v in raw_violations],
            checked_symbols=list(data.get("checked_symbols", [])),
            target_scope=data.get("target_scope"),
            summary=str(data.get("summary", "")),
        )

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serialize SymbolValidationReport to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
