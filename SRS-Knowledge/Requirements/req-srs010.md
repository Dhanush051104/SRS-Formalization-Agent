---
id: req-srs010
srs_id: "SRS010"
global_number: 6
source_number: 6
section: "3.2.1"
page: 15
patterns:
  - "[[pat-cardinality-threshold]]"
  - "[[pat-universal-quantification]]"
  - "[[pat-conditional-behavior]]"
  - "[[pat-graceful-degradation]]"
concepts:
  - "[[concept-fcp-fcr-architecture]]"
formalization:
  - "[[form-set-theory-rules]]"
dependencies:
  - "[[req-srs008]]"
  - "[[req-srs177]]"
---

# Requirement R6 SRS010

## Metadata
- **Global Requirement Number:** R6
- **Source/Local Requirement Number:** #6
- **SRS Identifier:** SRS010
- **Section:** 3.2.1
- **Page:** 15

## Source Requirement Text
> 6. System Initialization shall [SRS010] configure the FCP virtual group to use all available synchronized processors, if at least 3 of the 5 FCRs are active.

## Identified Patterns
- [[pat-cardinality-threshold]]
- [[pat-universal-quantification]]
- [[pat-conditional-behavior]]
- [[pat-graceful-degradation]]

## Relevant Concepts
- [[concept-fcp-fcr-architecture]]

## Relevant Formalization Notes
- [[form-set-theory-rules]]

## Known Dependencies
- [[req-srs008]]
- [[req-srs177]]

## Missing Parameters & Clarification Questions
- **Missing Parameters:** Missing explicit fallback behavior when fewer than 3 FCRs are active.
- **Clarification Questions:** Does system halt if active FCR count < 3?

## Known Inconsistencies & Issues
- None identified.
