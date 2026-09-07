---
id: req-srs178
srs_id: "SRS178"
global_number: 8
source_number: 8
section: "3.2.1"
page: 15
patterns:
  - "[[pat-timeout-deadline]]"
  - "[[pat-bounded-waiting]]"
  - "[[pat-failure-handling]]"
  - "[[pat-component-interaction]]"
  - "[[pat-cross-req-dependency]]"
concepts:
  - "[[concept-vmebus-ne-subsystem]]"
  - "[[concept-fcp-fcr-architecture]]"
formalization:
  - "[[form-timed-ltl-rules]]"
  - "[[form-fault-recovery]]"
dependencies:
  - "[[req-srs177]]"
---

# Requirement R8 SRS178

## Metadata
- **Global Requirement Number:** R8
- **Source/Local Requirement Number:** #8
- **SRS Identifier:** SRS178
- **Section:** 3.2.1
- **Page:** 15

## Source Requirement Text
> 8. If the failed FCP processor has not synced in 2.5 seconds after the surviving triplex has detected the loss of the FCP, then the surviving triplex shall [SRS178], within 1 second, send a single voted VMEbus reset through the NE to the failed FCP.

## Identified Patterns
- [[pat-timeout-deadline]]
- [[pat-bounded-waiting]]
- [[pat-failure-handling]]
- [[pat-component-interaction]]
- [[pat-cross-req-dependency]]

## Relevant Concepts
- [[concept-vmebus-ne-subsystem]]
- [[concept-fcp-fcr-architecture]]

## Relevant Formalization Notes
- [[form-timed-ltl-rules]]
- [[form-fault-recovery]]

## Known Dependencies
- [[req-srs177]]

## Missing Parameters & Clarification Questions
- **Missing Parameters:** Missing recovery behavior during the 1 second reset window.
- **Clarification Questions:** What if VMEbus reset fails to transmit?

## Known Inconsistencies & Issues
- None identified.
