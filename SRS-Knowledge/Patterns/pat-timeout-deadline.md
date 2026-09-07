---
id: pat-timeout-deadline
name: "Timeout / Deadline"
formalization_notes:
  - "[[form-timed-ltl-rules]]"
  - "[[form-metric-derivations]]"
concept_notes:
  - "[[concept-watchdog-timers]]"
  - "[[concept-50hz-timer-interrupt]]"
reference_requirements:
  - "[[req-srs178]]"
  - "[[req-srs297]]"
  - "[[req-srs189]]"
  - "[[req-srs015]]"
---

# Timeout / Deadline

## Definition
A hard real-time constraint requiring an action to complete within a strict time limit.

## Recognition Cues
Keywords and phrases indicative of this pattern:
- "within X seconds"
- "within 1 second"
- "take no longer than"
- "1.5 minutes"
- "after X seconds"

## Typical Structure
```text
Trigger Event (t0) -> System Action Completed by (t <= t0 + Deadline)
```

## Temporal / Mathematical Characteristics
- **Formal Expression Type:** Timed LTL Bounded Eventually (diamond_[0, T] P), Hard deadline bounds

## Formalization Relevance
When formalizing requirements matching this pattern, refer to the following formalization guidelines:
- [[form-timed-ltl-rules]]
- [[form-metric-derivations]]

## Related Patterns
- [[pat-bounded-waiting]]
- [[pat-lifecycle-boundary]]

## Reference Requirements
Requirements in the SRS that exhibit this pattern:
- [[req-srs178]]
- [[req-srs297]]
- [[req-srs189]]
- [[req-srs015]]

## Authoritative Notes
- Preserves explicit source semantics for domain reasoning.
- Supports automated context extraction by the Analyst Model.
