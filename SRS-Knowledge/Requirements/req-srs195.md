---
id: req-srs195
srs_id: "SRS195"
global_number: 22
source_number: 5
section: "3.2.2.1"
page: 16
patterns:
  - "[[pat-cardinality-threshold]]"
  - "[[pat-derived-math-constraint]]"
concepts:
  - "[[concept-vehicle-modes]]"
formalization:
  - "[[form-set-theory-rules]]"
dependencies:
  - "[[req-srs018]]"
  - "[[req-srs197]]"
---

# Requirement R22 SRS195

## Metadata
- **Global Requirement Number:** R22
- **Source/Local Requirement Number:** #5
- **SRS Identifier:** SRS195
- **Section:** 3.2.2.1
- **Page:** 16

## Source Requirement Text
> 5. The scheduler shall [SRS195] support up to 5 vehicle modes.

## Identified Patterns
- [[pat-cardinality-threshold]]
- [[pat-derived-math-constraint]]

## Relevant Concepts
- [[concept-vehicle-modes]]

## Relevant Formalization Notes
- [[form-set-theory-rules]]

## Known Dependencies
- [[req-srs018]]
- [[req-srs197]]

## Missing Parameters & Clarification Questions
- **Missing Parameters:** Missing vehicle mode enumeration IDs.
- **Clarification Questions:** What are the default vehicle modes?

## Known Inconsistencies & Issues
- None identified.
