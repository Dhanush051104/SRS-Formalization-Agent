---
id: pat-trigger-action
name: "Trigger -> Action"
formalization_notes:
  - "[[form-ltl-syntax-grammar]]"
  - "[[form-timed-ltl-rules]]"
concept_notes:
  - "[[concept-fcp-fcr-architecture]]"
  - "[[concept-icp-handshake]]"
reference_requirements:
  - "[[req-srs194]]"
  - "[[req-srs292]]"
  - "[[req-srs221]]"
---

# Trigger -> Action

## Definition
An event or state transition triggers a mandatory system action.

## Recognition Cues
Keywords and phrases indicative of this pattern:
- "whenever"
- "when"
- "on occurrence of"
- "upon receiving"
- "if ... then perform"

## Typical Structure
```text
Trigger Event (E) -> Mandatory Action (A)
```

## Temporal / Mathematical Characteristics
- **Formal Expression Type:** LTL Eventuality / Implication, Temporal bounds, Pre-state to Post-state transitions

## Formalization Relevance
When formalizing requirements matching this pattern, refer to the following formalization guidelines:
- [[form-ltl-syntax-grammar]]
- [[form-timed-ltl-rules]]

## Related Patterns
- [[pat-conditional-behavior]]
- [[pat-timeout-deadline]]

## Reference Requirements
Requirements in the SRS that exhibit this pattern:
- [[req-srs194]]
- [[req-srs292]]
- [[req-srs221]]

## Authoritative Notes
- Preserves explicit source semantics for domain reasoning.
- Supports automated context extraction by the Analyst Model.
