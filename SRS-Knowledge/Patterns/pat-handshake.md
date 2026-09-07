---
id: pat-handshake
name: "Handshake"
formalization_notes:
  - "[[form-timed-ltl-rules]]"
  - "[[form-api-specifications]]"
concept_notes:
  - "[[concept-icp-handshake]]"
reference_requirements:
  - "[[req-srs234]]"
  - "[[req-srs297]]"
  - "[[req-srs221]]"
  - "[[req-srs189]]"
---

# Handshake

## Definition
A two-way communication protocol where sender waits for acknowledgement signal from receiver.

## Recognition Cues
Keywords and phrases indicative of this pattern:
- "FCP Ready Sync"
- "ICP Ready signal"
- "wait for communication"
- "ack"
- "handshake"

## Typical Structure
```text
Sender sends Request -> Sender waits -> Receiver returns Response / Ready
```

## Temporal / Mathematical Characteristics
- **Formal Expression Type:** Paired LTL Request-Response formulas, State synchronization protocol

## Formalization Relevance
When formalizing requirements matching this pattern, refer to the following formalization guidelines:
- [[form-timed-ltl-rules]]
- [[form-api-specifications]]

## Related Patterns
- [[pat-component-interaction]]
- [[pat-bounded-waiting]]

## Reference Requirements
Requirements in the SRS that exhibit this pattern:
- [[req-srs234]]
- [[req-srs297]]
- [[req-srs221]]
- [[req-srs189]]

## Authoritative Notes
- Preserves explicit source semantics for domain reasoning.
- Supports automated context extraction by the Analyst Model.
