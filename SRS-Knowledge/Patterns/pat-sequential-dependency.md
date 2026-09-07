---
id: pat-sequential-dependency
name: "Sequential Dependency"
formalization_notes:
  - "[[form-ltl-syntax-grammar]]"
  - "[[form-api-specifications]]"
concept_notes:
  - "[[concept-fcp-fcr-architecture]]"
  - "[[concept-icp-handshake]]"
reference_requirements:
  - "[[req-srs234]]"
  - "[[req-srs215]]"
  - "[[req-srs221]]"
---

# Sequential Dependency

## Definition
A sequence of operations where step N must complete before step N+1 can execute.

## Recognition Cues
Keywords and phrases indicative of this pattern:
- "followed by"
- "after completing"
- "prior to"
- "then"
- "subsequently"

## Typical Structure
```text
Step A completes -> Step B initiated -> Step C initiated
```

## Temporal / Mathematical Characteristics
- **Formal Expression Type:** LTL Precedence (G(B -> O A)), Strict Ordering, State Machine Transitions

## Formalization Relevance
When formalizing requirements matching this pattern, refer to the following formalization guidelines:
- [[form-ltl-syntax-grammar]]
- [[form-api-specifications]]

## Related Patterns
- [[pat-completion-barrier]]
- [[pat-handshake]]

## Reference Requirements
Requirements in the SRS that exhibit this pattern:
- [[req-srs234]]
- [[req-srs215]]
- [[req-srs221]]

## Authoritative Notes
- Preserves explicit source semantics for domain reasoning.
- Supports automated context extraction by the Analyst Model.
