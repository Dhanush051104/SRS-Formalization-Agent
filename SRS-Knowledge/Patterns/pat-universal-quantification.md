---
id: pat-universal-quantification
name: "Universal Quantification"
formalization_notes:
  - "[[form-set-theory-rules]]"
concept_notes:
  - "[[concept-fcp-fcr-architecture]]"
  - "[[concept-vmebus-ne-subsystem]]"
reference_requirements:
  - "[[req-srs010]]"
  - "[[req-srs011]]"
  - "[[req-srs296]]"
---

# Universal Quantification

## Definition
A property or constraint that must hold for ALL members of a set or channel group.

## Recognition Cues
Keywords and phrases indicative of this pattern:
- "all"
- "each"
- "every"
- "all available"
- "all channels"
- "for all"

## Typical Structure
```text
For all x in S: P(x) holds continuously or upon trigger
```

## Temporal / Mathematical Characteristics
- **Formal Expression Type:** First-Order Logic Universal Quantifier (forall x in S), Invariant assertions

## Formalization Relevance
When formalizing requirements matching this pattern, refer to the following formalization guidelines:
- [[form-set-theory-rules]]

## Related Patterns
- [[pat-set-construction]]
- [[pat-cardinality-threshold]]

## Reference Requirements
Requirements in the SRS that exhibit this pattern:
- [[req-srs010]]
- [[req-srs011]]
- [[req-srs296]]

## Authoritative Notes
- Preserves explicit source semantics for domain reasoning.
- Supports automated context extraction by the Analyst Model.
