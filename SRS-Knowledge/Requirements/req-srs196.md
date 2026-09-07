---
id: req-srs196
srs_id: "SRS196"
global_number: 19
source_number: 2
section: "3.2.2.1"
page: 16
patterns:
  - "[[pat-cardinality-threshold]]"
  - "[[pat-derived-math-constraint]]"
  - "[[pat-state-consistency]]"
concepts:
  - "[[concept-rate-groups-tasks]]"
formalization:
  - "[[form-set-theory-rules]]"
dependencies:
  - "[[req-srs017]]"
---

# Requirement R19 SRS196

## Metadata
- **Global Requirement Number:** R19
- **Source/Local Requirement Number:** #2
- **SRS Identifier:** SRS196
- **Section:** 3.2.2.1
- **Page:** 16

## Source Requirement Text
> 2. The scheduler shall [SRS196] support up to 20 tasks per rate group.

## Identified Patterns
- [[pat-cardinality-threshold]]
- [[pat-derived-math-constraint]]
- [[pat-state-consistency]]

## Relevant Concepts
- [[concept-rate-groups-tasks]]

## Relevant Formalization Notes
- [[form-set-theory-rules]]

## Known Dependencies
- [[req-srs017]]

## Missing Parameters & Clarification Questions
- **Missing Parameters:** Missing error return code when 21st task is installed.
- **Clarification Questions:** Are 20 tasks per rate group statically allocated?

## Known Inconsistencies & Issues
- None identified.
