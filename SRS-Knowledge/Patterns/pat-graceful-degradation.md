---
id: pat-graceful-degradation
name: "Fallback / Graceful Degradation"
formalization_notes:
  - "[[form-fault-recovery]]"
  - "[[form-set-theory-rules]]"
concept_notes:
  - "[[concept-fcp-fcr-architecture]]"
  - "[[concept-vmebus-ne-subsystem]]"
reference_requirements:
  - "[[req-srs010]]"
  - "[[req-srs189]]"
  - "[[req-srs243]]"
---

# Fallback / Graceful Degradation

## Definition
Maintaining partial system operation when a sub-component fails or is missing.

## Recognition Cues
Keywords and phrases indicative of this pattern:
- "mask out that ICP, but continue to use"
- "use all available"
- "will not fail the FCR"
- "defer to presence test"

## Typical Structure
```text
Component_Failed -> Reconfigure Available Pool -> Continue Operation Degraded
```

## Temporal / Mathematical Characteristics
- **Formal Expression Type:** Degraded Mode Predicates, Reduced Set Cardinality Operation

## Formalization Relevance
When formalizing requirements matching this pattern, refer to the following formalization guidelines:
- [[form-fault-recovery]]
- [[form-set-theory-rules]]

## Related Patterns
- [[pat-failure-handling]]
- [[pat-cardinality-threshold]]

## Reference Requirements
Requirements in the SRS that exhibit this pattern:
- [[req-srs010]]
- [[req-srs189]]
- [[req-srs243]]

## Authoritative Notes
- Preserves explicit source semantics for domain reasoning.
- Supports automated context extraction by the Analyst Model.
