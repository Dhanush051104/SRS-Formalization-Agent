---
id: pat-simultaneous-actions
name: "Multiple Simultaneous Actions"
formalization_notes:
  - "[[form-ltl-syntax-grammar]]"
  - "[[form-api-specifications]]"
concept_notes:
  - "[[concept-rate-groups-tasks]]"
  - "[[concept-50hz-timer-interrupt]]"
reference_requirements:
  - "[[req-srs215]]"
  - "[[req-srs199]]"
---

# Multiple Simultaneous Actions

## Definition
A single requirement specifies multiple actions that must occur concurrently or in one call.

## Recognition Cues
Keywords and phrases indicative of this pattern:
- "create tasks, create communication sockets, initialize vehicle mode"
- "start 50 Hz timer and enable timer interrupt"
- "enable and reset"

## Typical Structure
```text
Action_1 AND Action_2 AND Action_3 invoked simultaneously
```

## Temporal / Mathematical Characteristics
- **Formal Expression Type:** Logical Conjunction of Post-States (Post_1 /\ Post_2 /\ Post_3)

## Formalization Relevance
When formalizing requirements matching this pattern, refer to the following formalization guidelines:
- [[form-ltl-syntax-grammar]]
- [[form-api-specifications]]

## Related Patterns
- [[pat-api-invocation]]
- [[pat-trigger-action]]

## Reference Requirements
Requirements in the SRS that exhibit this pattern:
- [[req-srs215]]
- [[req-srs199]]

## Authoritative Notes
- Preserves explicit source semantics for domain reasoning.
- Supports automated context extraction by the Analyst Model.
