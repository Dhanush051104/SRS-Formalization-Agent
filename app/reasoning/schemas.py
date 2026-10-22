import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


class ReasoningError(Exception):
    """Base exception for all Reasoning module errors."""
    pass


class ReasoningValidationError(ReasoningError):
    """Raised when Reasoning output fails schema validation, JSON structure, or field constraints."""
    pass


class ProvenanceCategory:
    """Canonical categories for constraint and parameter provenance."""
    EXPLICIT_SOURCE = "EXPLICIT_SOURCE"
    SUPPORTED_DEPENDENCY = "SUPPORTED_DEPENDENCY"
    APPROVED_DERIVATION = "APPROVED_DERIVATION"
    UNRESOLVED = "UNRESOLVED"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass
class ConstraintProvenance:
    """
    Explicit provenance record tracking the origin and justification of a constraint or parameter.
    """
    constraint_id: str
    statement: str
    category: str = ProvenanceCategory.EXPLICIT_SOURCE
    source_text: Optional[str] = None
    justification: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "constraint_id": self.constraint_id,
            "statement": self.statement,
            "category": self.category,
            "source_text": self.source_text,
            "justification": self.justification,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConstraintProvenance":
        return cls(
            constraint_id=str(data.get("constraint_id", "")),
            statement=str(data.get("statement", "")),
            category=str(data.get("category", ProvenanceCategory.EXPLICIT_SOURCE)),
            source_text=data.get("source_text"),
            justification=str(data.get("justification", "")),
        )


@dataclass
class PropositionDefinition:
    """
    Structured definition of an atomic proposition with explicit mathematical definition notation.
    Example: symbol='P', definition='Power-on reset occurred', notation='P := Power-on reset occurred'.
    """
    symbol: str
    definition: str
    notation: str = ""
    source_reference: Optional[str] = None
    provenance: str = "EXPLICIT_SOURCE"
    user_approved: bool = False

    def __post_init__(self):
        if not self.notation and self.symbol and self.definition:
            self.notation = f"{self.symbol} := {self.definition}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "definition": self.definition,
            "notation": self.notation,
            "source_reference": self.source_reference,
            "provenance": self.provenance,
            "user_approved": self.user_approved,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PropositionDefinition":
        sym = str(data.get("symbol", "")).strip()
        defn = str(data.get("definition", "")).strip()
        notat = str(data.get("notation", "")).strip()
        if not notat and sym and defn:
            notat = f"{sym} := {defn}"
        return cls(
            symbol=sym,
            definition=defn,
            notation=notat,
            source_reference=data.get("source_reference"),
            provenance=str(data.get("provenance", "EXPLICIT_SOURCE")),
            user_approved=bool(data.get("user_approved", False)),
        )


@dataclass
class PredicateDefinition:
    """
    Structured definition of a domain or state predicate with explicit arguments.
    """
    name: str
    entity: str = ""
    arguments: List[str] = field(default_factory=list)
    condition_type: str = "STATE"  # TRIGGER, PRECONDITION, ACTION, POSTCONDITION, STATE
    description: str = ""
    formal_expression: Optional[str] = None
    notation: str = ""
    source_reference: Optional[str] = None
    provenance: str = "EXPLICIT_SOURCE"
    user_approved: bool = False

    def __post_init__(self):
        if not self.notation and self.name:
            args_str = f"({', '.join(self.arguments)})" if self.arguments else ""
            desc = self.description or self.formal_expression or ""
            if desc:
                self.notation = f"{self.name}{args_str} := {desc}"
            else:
                self.notation = f"{self.name}{args_str}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "entity": self.entity,
            "arguments": list(self.arguments),
            "condition_type": self.condition_type,
            "description": self.description,
            "formal_expression": self.formal_expression,
            "notation": self.notation,
            "source_reference": self.source_reference,
            "provenance": self.provenance,
            "user_approved": self.user_approved,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PredicateDefinition":
        args_raw = data.get("arguments", [])
        args = [str(a) for a in args_raw] if isinstance(args_raw, list) else []
        name = str(data.get("name", "")).strip()
        desc = str(data.get("description", "")).strip()
        f_expr = data.get("formal_expression")
        notat = str(data.get("notation", "")).strip()
        if not notat and name:
            args_str = f"({', '.join(args)})" if args else ""
            target_desc = desc or f_expr or ""
            if target_desc:
                notat = f"{name}{args_str} := {target_desc}"
            else:
                notat = f"{name}{args_str}"

        return cls(
            name=name,
            entity=str(data.get("entity", "")).strip(),
            arguments=args,
            condition_type=str(data.get("condition_type", "STATE")),
            description=desc,
            formal_expression=f_expr,
            notation=notat,
            source_reference=data.get("source_reference"),
            provenance=str(data.get("provenance", "EXPLICIT_SOURCE")),
            user_approved=bool(data.get("user_approved", False)),
        )


@dataclass
class DomainEntityDefinition:
    """
    Domain entity or variable referenced in the formalization.
    """
    name: str
    category: str = "ENTITY"  # ENTITY, VARIABLE, CONSTANT
    description: str = ""
    source_reference: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "source_reference": self.source_reference,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DomainEntityDefinition":
        return cls(
            name=str(data.get("name", "")).strip(),
            category=str(data.get("category", "ENTITY")).strip(),
            description=str(data.get("description", "")).strip(),
            source_reference=data.get("source_reference"),
        )


@dataclass
class IntermediateRepresentation:
    """
    Intermediate structured representation separating atomic propositions, predicates,
    domain entities, variables, temporal composition rules, and formula construction.
    """
    propositions: List[PropositionDefinition] = field(default_factory=list)
    predicates: List[PredicateDefinition] = field(default_factory=list)
    entities: List[DomainEntityDefinition] = field(default_factory=list)
    temporal_operators: List[str] = field(default_factory=list)
    atomic_clauses: List[str] = field(default_factory=list)
    composition_rules: List[str] = field(default_factory=list)
    formula_construction: str = ""
    unresolved_parameters: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "propositions": [p.to_dict() if hasattr(p, "to_dict") else p for p in self.propositions],
            "predicates": [p.to_dict() if hasattr(p, "to_dict") else p for p in self.predicates],
            "entities": [e.to_dict() if hasattr(e, "to_dict") else e for e in self.entities],
            "temporal_operators": list(self.temporal_operators),
            "atomic_clauses": list(self.atomic_clauses or [p.notation or f"{p.symbol} := {p.definition}" for p in self.propositions]),
            "composition_rules": list(self.composition_rules),
            "formula_construction": self.formula_construction,
            "unresolved_parameters": list(self.unresolved_parameters),
        }

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IntermediateRepresentation":
        # Parse propositions
        raw_props = data.get("propositions", [])
        props: List[PropositionDefinition] = []
        if isinstance(raw_props, list):
            for p in raw_props:
                if isinstance(p, dict):
                    props.append(PropositionDefinition.from_dict(p))
                elif isinstance(p, PropositionDefinition):
                    props.append(p)
                elif isinstance(p, str) and p.strip():
                    if ":=" in p:
                        sym, defn = p.split(":=", 1)
                        props.append(PropositionDefinition(symbol=sym.strip(), definition=defn.strip(), notation=p.strip()))
                    else:
                        props.append(PropositionDefinition(symbol=p.strip(), definition=p.strip(), notation=p.strip()))

        # Fallback from atomic_clauses if propositions empty
        raw_atomic = data.get("atomic_clauses", [])
        if not props and isinstance(raw_atomic, list):
            for ac in raw_atomic:
                if isinstance(ac, str) and ac.strip():
                    if ":=" in ac:
                        sym, defn = ac.split(":=", 1)
                        props.append(PropositionDefinition(symbol=sym.strip(), definition=defn.strip(), notation=ac.strip()))
                    else:
                        props.append(PropositionDefinition(symbol=ac.strip(), definition=ac.strip(), notation=ac.strip()))

        # Parse predicates
        raw_preds = data.get("predicates", [])
        preds: List[PredicateDefinition] = []
        if isinstance(raw_preds, list):
            for p in raw_preds:
                if isinstance(p, dict):
                    preds.append(PredicateDefinition.from_dict(p))
                elif isinstance(p, PredicateDefinition):
                    preds.append(p)
                elif isinstance(p, str) and p.strip():
                    preds.append(PredicateDefinition(name=p.strip(), description=p.strip()))

        # Parse entities
        raw_entities = data.get("entities", [])
        entities: List[DomainEntityDefinition] = []
        if isinstance(raw_entities, list):
            for e in raw_entities:
                if isinstance(e, dict):
                    entities.append(DomainEntityDefinition.from_dict(e))
                elif isinstance(e, DomainEntityDefinition):
                    entities.append(e)
                elif isinstance(e, str) and e.strip():
                    entities.append(DomainEntityDefinition(name=e.strip()))

        temp_ops = [str(x) for x in data.get("temporal_operators", [])] if isinstance(data.get("temporal_operators"), list) else []
        atomic_clauses = [str(x) for x in raw_atomic] if isinstance(raw_atomic, list) else []
        comp_rules = [str(x) for x in data.get("composition_rules", [])] if isinstance(data.get("composition_rules"), list) else []
        formula_construction = str(data.get("formula_construction", "")).strip()
        unresolved_params = [str(x) for x in data.get("unresolved_parameters", [])] if isinstance(data.get("unresolved_parameters"), list) else []

        return cls(
            propositions=props,
            predicates=preds,
            entities=entities,
            temporal_operators=temp_ops,
            atomic_clauses=atomic_clauses,
            composition_rules=comp_rules,
            formula_construction=formula_construction,
            unresolved_parameters=unresolved_params,
        )


@dataclass
class ReasoningResult:
    """
    Structured result produced by a ReasoningModel after processing a ContextPackage.
    Captures formalization, logical components, assumptions, unresolved items, and provenance.
    """
    requirement_id: int
    global_number: int
    srs_id: str
    interpretation: str = ""
    identified_entities: List[str] = field(default_factory=list)
    predicates: List[str] = field(default_factory=list)
    conditions: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    temporal_constraints: List[str] = field(default_factory=list)
    mathematical_constraints: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    formalization: str = ""
    assumptions: List[str] = field(default_factory=list)
    unresolved_items: List[str] = field(default_factory=list)
    reasoning_notes: Optional[str] = None
    provenance: Dict[str, Any] = field(default_factory=dict)
    raw_model_response: Optional[str] = None
    constraint_provenance: List[Dict[str, Any]] = field(default_factory=list)
    intermediate_representation: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert the ReasoningResult instance to a Python dictionary."""
        return {
            "requirement_id": self.requirement_id,
            "global_number": self.global_number,
            "srs_id": self.srs_id,
            "interpretation": self.interpretation,
            "identified_entities": self.identified_entities,
            "predicates": self.predicates,
            "conditions": self.conditions,
            "actions": self.actions,
            "temporal_constraints": self.temporal_constraints,
            "mathematical_constraints": self.mathematical_constraints,
            "dependencies": self.dependencies,
            "formalization": self.formalization,
            "assumptions": self.assumptions,
            "unresolved_items": self.unresolved_items,
            "reasoning_notes": self.reasoning_notes,
            "provenance": self.provenance,
            "raw_model_response": self.raw_model_response,
            "constraint_provenance": self.constraint_provenance,
            "intermediate_representation": (
                self.intermediate_representation.to_dict()
                if hasattr(self.intermediate_representation, "to_dict")
                else self.intermediate_representation
            ),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], raw_response: Optional[str] = None) -> "ReasoningResult":
        """
        Construct a ReasoningResult instance from a dictionary.

        Args:
            data: Dictionary containing expected keys.
            raw_response: Optional raw JSON text returned by model.

        Returns:
            ReasoningResult instance.
        """
        def _get_list(key: str) -> List[str]:
            val = data.get(key, [])
            if val is None:
                return []
            if not isinstance(val, list):
                raise ReasoningValidationError(f"ReasoningResult field '{key}' must be a list of strings, got {type(val).__name__}.")
            return [str(x) for x in val]

        ir_raw = data.get("intermediate_representation")
        ir_parsed = None
        if isinstance(ir_raw, dict):
            ir_parsed = IntermediateRepresentation.from_dict(ir_raw)
        elif isinstance(ir_raw, IntermediateRepresentation):
            ir_parsed = ir_raw
        elif ir_raw is not None:
            ir_parsed = ir_raw

        req_id = data.get("requirement_id")
        if req_id is None:
            req_id = data.get("id") or data.get("req_id")
        if req_id is None:
            raise ReasoningValidationError("ReasoningResult missing required field 'requirement_id'.")
        try:
            req_id_int = int(req_id)
        except (ValueError, TypeError):
            raise ReasoningValidationError(f"ReasoningResult field 'requirement_id' must be an integer, got {req_id!r}.")

        global_num = data.get("global_number")
        if global_num is None:
            global_num = data.get("global_num") or data.get("number")
        if global_num is None:
            raise ReasoningValidationError("ReasoningResult missing required field 'global_number'.")
        try:
            global_num_int = int(global_num)
        except (ValueError, TypeError):
            raise ReasoningValidationError(f"ReasoningResult field 'global_number' must be an integer, got {global_num!r}.")

        srs_id = data.get("srs_id")
        if srs_id is None:
            srs_id = data.get("srsId") or data.get("req_srs_id")
        if srs_id is None:
            raise ReasoningValidationError("ReasoningResult missing required field 'srs_id'.")

        return cls(
            requirement_id=req_id_int,
            global_number=global_num_int,
            srs_id=str(srs_id),
            interpretation=str(data.get("interpretation", "")),
            identified_entities=_get_list("identified_entities"),
            predicates=_get_list("predicates"),
            conditions=_get_list("conditions"),
            actions=_get_list("actions"),
            temporal_constraints=_get_list("temporal_constraints"),
            mathematical_constraints=_get_list("mathematical_constraints"),
            dependencies=_get_list("dependencies"),
            formalization=str(data.get("formalization", "")),
            assumptions=_get_list("assumptions"),
            unresolved_items=_get_list("unresolved_items"),
            reasoning_notes=data.get("reasoning_notes"),
            provenance=dict(data.get("provenance", {})),
            raw_model_response=raw_response or data.get("raw_model_response"),
            constraint_provenance=list(data.get("constraint_provenance", []) or []),
            intermediate_representation=ir_parsed,
        )

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serialize the ReasoningResult to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> "ReasoningResult":
        """Parse a JSON string into a ReasoningResult instance."""
        try:
            data = json.loads(json_str)
            return cls.from_dict(data, raw_response=json_str)
        except Exception as e:
            raise ReasoningValidationError(f"Failed to parse ReasoningResult from JSON string: {e}")
