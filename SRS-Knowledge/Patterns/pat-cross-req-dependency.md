---
id: pat-cross-req-dependency
name: "Cross-Requirement Dependency"
formalization_notes:
  - "[[form-ltl-syntax-grammar]]"
  - "[[form-metric-derivations]]"
concept_notes:
  - "[[concept-icp-handshake]]"
  - "[[concept-50hz-timer-interrupt]]"
reference_requirements:
  - "[[req-srs178]]"
  - "[[req-srs221]]"
  - "[[req-srs015]]"
---

# Cross-Requirement Dependency

## Definition
A requirement explicitly or implicitly references or constrains another requirement's state.

## Recognition Cues
Keywords and phrases indicative of this pattern:
- "after ... has detected"
- "from the sending of"
- "bounds"
- "constrained by"

## Typical Structure
```text
Req_B relies on State / Output from Req_A
```

## Temporal / Mathematical Characteristics
- **Formal Expression Type:** Cross-Requirement LTL Invariants, Global Traceability Chains

## Formalization Relevance
When formalizing requirements matching this pattern, refer to the following formalization guidelines:
- [[form-ltl-syntax-grammar]]
- [[form-metric-derivations]]

## Related Patterns
- [[pat-sequential-dependency]]
- [[pat-lifecycle-boundary]]

## Reference Requirements
Requirements in the SRS that exhibit this pattern:
- [[req-srs178]]
- [[req-srs221]]
- [[req-srs015]]

## Authoritative Notes
- Preserves explicit source semantics for domain reasoning.
- Supports automated context extraction by the Analyst Model.
