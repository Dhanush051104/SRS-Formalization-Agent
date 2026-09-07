---
id: pat-state-consistency
name: "State Consistency / Equality"
formalization_notes:
  - "[[form-set-theory-rules]]"
concept_notes:
  - "[[concept-fcp-fcr-architecture]]"
reference_requirements:
  - "[[req-srs011]]"
  - "[[req-srs196]]"
  - "[[req-srs197]]"
---

# State Consistency / Equality

## Definition
Ensuring multiple redundant units or state variables maintain identical values/registers.

## Recognition Cues
Keywords and phrases indicative of this pattern:
- "align processor state"
- "congruent aligned"
- "identical"
- "equal"
- "remain synchronized"

## Typical Structure
```text
For all i, j in ActiveGroup: State(Unit_i) == State(Unit_j)
```

## Temporal / Mathematical Characteristics
- **Formal Expression Type:** Equivalence relations, Invariant State Equality, Synchronization invariants

## Formalization Relevance
When formalizing requirements matching this pattern, refer to the following formalization guidelines:
- [[form-set-theory-rules]]

## Related Patterns
- [[pat-universal-quantification]]
- [[pat-derived-math-constraint]]

## Reference Requirements
Requirements in the SRS that exhibit this pattern:
- [[req-srs011]]
- [[req-srs196]]
- [[req-srs197]]

## Authoritative Notes
- Preserves explicit source semantics for domain reasoning.
- Supports automated context extraction by the Analyst Model.
