---
id: pat-bounded-waiting
name: "Bounded Waiting"
formalization_notes:
  - "[[form-timed-ltl-rules]]"
  - "[[form-metric-derivations]]"
concept_notes:
  - "[[concept-icp-handshake]]"
  - "[[concept-watchdog-timers]]"
reference_requirements:
  - "[[req-srs008]]"
  - "[[req-srs178]]"
  - "[[req-srs297]]"
  - "[[req-srs189]]"
---

# Bounded Waiting

## Definition
The system pauses execution waiting for an event up to a specified maximum duration.

## Recognition Cues
Keywords and phrases indicative of this pattern:
- "wait up to X seconds"
- "wait for up to"
- "in the presence of skew of X seconds"

## Typical Structure
```text
State = Waiting -> (Event_Occurs OR Elapsed_Time >= Timeout)
```

## Temporal / Mathematical Characteristics
- **Formal Expression Type:** Timed LTL Bounded Operators, Upper bounded waiting intervals [0, T]

## Formalization Relevance
When formalizing requirements matching this pattern, refer to the following formalization guidelines:
- [[form-timed-ltl-rules]]
- [[form-metric-derivations]]

## Related Patterns
- [[pat-timeout-deadline]]
- [[pat-handshake]]

## Reference Requirements
Requirements in the SRS that exhibit this pattern:
- [[req-srs008]]
- [[req-srs178]]
- [[req-srs297]]
- [[req-srs189]]

## Authoritative Notes
- Preserves explicit source semantics for domain reasoning.
- Supports automated context extraction by the Analyst Model.
