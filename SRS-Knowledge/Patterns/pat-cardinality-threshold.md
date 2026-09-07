---
id: pat-cardinality-threshold
name: "Cardinality / Threshold"
formalization_notes:
  - "[[form-set-theory-rules]]"
  - "[[form-metric-derivations]]"
concept_notes:
  - "[[concept-fcp-fcr-architecture]]"
  - "[[concept-rate-groups-tasks]]"
  - "[[concept-vehicle-modes]]"
reference_requirements:
  - "[[req-srs010]]"
  - "[[req-srs196]]"
  - "[[req-srs197]]"
  - "[[req-srs195]]"
---

# Cardinality / Threshold

## Definition
A constraint specifying a numerical minimum, maximum, or voting threshold on elements.

## Recognition Cues
Keywords and phrases indicative of this pattern:
- "at least X of Y"
- "up to N"
- "no more than N"
- "maximum of N"

## Typical Structure
```text
Count(Set) >= Min_Threshold  OR  Count(Set) <= Max_Threshold
```

## Temporal / Mathematical Characteristics
- **Formal Expression Type:** Set Cardinality inequalities (|S| >= k), Boundary integer arithmetic

## Formalization Relevance
When formalizing requirements matching this pattern, refer to the following formalization guidelines:
- [[form-set-theory-rules]]
- [[form-metric-derivations]]

## Related Patterns
- [[pat-set-construction]]
- [[pat-derived-math-constraint]]

## Reference Requirements
Requirements in the SRS that exhibit this pattern:
- [[req-srs010]]
- [[req-srs196]]
- [[req-srs197]]
- [[req-srs195]]

## Authoritative Notes
- Preserves explicit source semantics for domain reasoning.
- Supports automated context extraction by the Analyst Model.
