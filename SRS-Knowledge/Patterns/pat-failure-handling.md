---
id: pat-failure-handling
name: "Failure Handling"
formalization_notes:
  - "[[form-fault-recovery]]"
concept_notes:
  - "[[concept-watchdog-timers]]"
  - "[[concept-vmebus-ne-subsystem]]"
reference_requirements:
  - "[[req-srs292]]"
  - "[[req-srs177]]"
  - "[[req-srs178]]"
  - "[[req-srs243]]"
---

# Failure Handling

## Definition
Actions taken by the system when a hardware, software, or timing fault occurs.

## Recognition Cues
Keywords and phrases indicative of this pattern:
- "fault"
- "failed FCP"
- "has not synced"
- "fails to send"
- "mask out"

## Typical Structure
```text
Fault Detected -> Isolation / Reset / Masking Action -> Recovery Mode
```

## Temporal / Mathematical Characteristics
- **Formal Expression Type:** Fault Predicates, Error State Machine Transitions, Isolation rules

## Formalization Relevance
When formalizing requirements matching this pattern, refer to the following formalization guidelines:
- [[form-fault-recovery]]

## Related Patterns
- [[pat-graceful-degradation]]
- [[pat-conditional-behavior]]

## Reference Requirements
Requirements in the SRS that exhibit this pattern:
- [[req-srs292]]
- [[req-srs177]]
- [[req-srs178]]
- [[req-srs243]]

## Authoritative Notes
- Preserves explicit source semantics for domain reasoning.
- Supports automated context extraction by the Analyst Model.
