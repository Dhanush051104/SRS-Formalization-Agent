---
id: req-srs197
srs_id: "SRS197"
global_number: 21
source_number: 4
section: "3.2.2.1"
page: 16
patterns:
  - "[[pat-cardinality-threshold]]"
  - "[[pat-derived-math-constraint]]"
  - "[[pat-state-consistency]]"
concepts:
  - "[[concept-vehicle-modes]]"
  - "[[concept-rate-groups-tasks]]"
formalization:
  - "[[form-set-theory-rules]]"
dependencies:
  - "[[req-srs018]]"
---

# Requirement R21 SRS197

## Metadata
- **Global Requirement Number:** R21
- **Source/Local Requirement Number:** #4
- **SRS Identifier:** SRS197
- **Section:** 3.2.2.1
- **Page:** 16

## Source Requirement Text
> 4. The scheduler shall [SRS197] support up to 3 rate groups per vehicle mode.

## Identified Patterns
- [[pat-cardinality-threshold]]
- [[pat-derived-math-constraint]]
- [[pat-state-consistency]]

## Relevant Concepts
- [[concept-vehicle-modes]]
- [[concept-rate-groups-tasks]]

## Relevant Formalization Notes
- [[form-set-theory-rules]]

## Known Dependencies
- [[req-srs018]]

## Missing Parameters & Clarification Questions
- **Missing Parameters:** Missing overflow error behavior.
- **Clarification Questions:** Are rate group IDs fixed (e.g. 50Hz, 10Hz, 1Hz)?

## Known Inconsistencies & Issues
- None identified.
