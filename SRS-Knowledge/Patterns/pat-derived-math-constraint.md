---
id: pat-derived-math-constraint
name: "Derived Mathematical Constraint"
formalization_notes:
  - "[[form-metric-derivations]]"
  - "[[form-set-theory-rules]]"
concept_notes:
  - "[[concept-fcp-fcr-architecture]]"
  - "[[concept-rate-groups-tasks]]"
  - "[[concept-vehicle-modes]]"
reference_requirements:
  - "[[req-srs008]]"
  - "[[req-srs196]]"
  - "[[req-srs197]]"
  - "[[req-srs195]]"
---

# Derived Mathematical Constraint

## Definition
An implicit or explicit quantitative relation (skew, rate calculation, scaling factor).

## Recognition Cues
Keywords and phrases indicative of this pattern:
- "skew of 2.5 seconds"
- "pairwise maximum skew"
- "support up to N"
- "50 Hz timer"

## Typical Structure
```text
Variable <= Formula(Params)  OR  Delta_T <= Max_Skew
```

## Temporal / Mathematical Characteristics
- **Formal Expression Type:** Linear Arithmetic Constraints, Real/Integer Variable Bounds

## Formalization Relevance
When formalizing requirements matching this pattern, refer to the following formalization guidelines:
- [[form-metric-derivations]]
- [[form-set-theory-rules]]

## Related Patterns
- [[pat-cardinality-threshold]]
- [[pat-state-consistency]]

## Reference Requirements
Requirements in the SRS that exhibit this pattern:
- [[req-srs008]]
- [[req-srs196]]
- [[req-srs197]]
- [[req-srs195]]

## Authoritative Notes
- Preserves explicit source semantics for domain reasoning.
- Supports automated context extraction by the Analyst Model.
