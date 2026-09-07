---
id: pat-conditional-behavior
name: "Conditional Behavior"
formalization_notes:
  - "[[form-ltl-syntax-grammar]]"
  - "[[form-fault-recovery]]"
concept_notes:
  - "[[concept-fcp-fcr-architecture]]"
  - "[[concept-vmebus-ne-subsystem]]"
reference_requirements:
  - "[[req-srs292]]"
  - "[[req-srs010]]"
  - "[[req-srs177]]"
  - "[[req-srs243]]"
---

# Conditional Behavior

## Definition
System behavior branches based on whether a boolean precondition or status is met.

## Recognition Cues
Keywords and phrases indicative of this pattern:
- "if"
- "if at least"
- "if any of"
- "if the failed"
- "if the NEFU ICP fails"

## Typical Structure
```text
IF Condition C IS TRUE THEN Action A ELSE Action B
```

## Temporal / Mathematical Characteristics
- **Formal Expression Type:** Guard Predicates, Branching Logic (C -> A and not C -> B)

## Formalization Relevance
When formalizing requirements matching this pattern, refer to the following formalization guidelines:
- [[form-ltl-syntax-grammar]]
- [[form-fault-recovery]]

## Related Patterns
- [[pat-trigger-action]]
- [[pat-failure-handling]]

## Reference Requirements
Requirements in the SRS that exhibit this pattern:
- [[req-srs292]]
- [[req-srs010]]
- [[req-srs177]]
- [[req-srs243]]

## Authoritative Notes
- Preserves explicit source semantics for domain reasoning.
- Supports automated context extraction by the Analyst Model.
