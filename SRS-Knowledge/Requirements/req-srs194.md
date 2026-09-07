---
id: req-srs194
srs_id: "SRS194"
global_number: 1
source_number: 1
section: "3.2.1"
page: 15
patterns:
  - "[[pat-trigger-action]]"
  - "[[pat-initialization]]"
  - "[[pat-lifecycle-boundary]]"
  - "[[pat-completion-barrier]]"
concepts:
  - "[[concept-fcp-fcr-architecture]]"
formalization:
  - "[[form-api-specifications]]"
dependencies:
  - "[[req-srs234]]"
  - "[[req-srs014]]"
  - "[[req-srs292]]"
  - "[[req-srs008]]"
  - "[[req-srs010]]"
  - "[[req-srs177]]"
  - "[[req-srs178]]"
  - "[[req-srs011]]"
  - "[[req-srs296]]"
  - "[[req-srs297]]"
  - "[[req-srs215]]"
  - "[[req-srs221]]"
  - "[[req-srs189]]"
  - "[[req-srs243]]"
  - "[[req-srs199]]"
---

# Requirement R1 SRS194

## Metadata
- **Global Requirement Number:** R1
- **Source/Local Requirement Number:** #1
- **SRS Identifier:** SRS194
- **Section:** 3.2.1
- **Page:** 15

## Source Requirement Text
> 1. Whenever a power-on reset occurs, System Initialization shall [SRS194] perform the following functions.

## Identified Patterns
- [[pat-trigger-action]]
- [[pat-initialization]]
- [[pat-lifecycle-boundary]]
- [[pat-completion-barrier]]

## Relevant Concepts
- [[concept-fcp-fcr-architecture]]

## Relevant Formalization Notes
- [[form-api-specifications]]

## Known Dependencies
- [[req-srs234]]
- [[req-srs014]]
- [[req-srs292]]
- [[req-srs008]]
- [[req-srs010]]
- [[req-srs177]]
- [[req-srs178]]
- [[req-srs011]]
- [[req-srs296]]
- [[req-srs297]]
- [[req-srs215]]
- [[req-srs221]]
- [[req-srs189]]
- [[req-srs243]]
- [[req-srs199]]

## Missing Parameters & Clarification Questions
- **Missing Parameters:** Does not explicitly enumerate the complete list of sub-functions in the same statement (relies on R2-R16).
- **Clarification Questions:** Are sub-functions executed synchronously or asynchronously?

## Known Inconsistencies & Issues
- INC-001: Q30 is defined twice / appears both as an R1 boundary and an R16 implication.
