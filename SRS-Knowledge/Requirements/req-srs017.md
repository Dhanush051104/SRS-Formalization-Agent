---
id: req-srs017
srs_id: "SRS017"
global_number: 18
source_number: 1
section: "3.2.2.1"
page: 16
patterns:
  - "[[pat-api-invocation]]"
  - "[[pat-lifecycle-boundary]]"
  - "[[pat-component-interaction]]"
concepts:
  - "[[concept-rate-groups-tasks]]"
formalization:
  - "[[form-api-specifications]]"
dependencies:
  - "[[req-srs196]]"
---

# Requirement R18 SRS017

## Metadata
- **Global Requirement Number:** R18
- **Source/Local Requirement Number:** #1
- **SRS Identifier:** SRS017
- **Section:** 3.2.2.1
- **Page:** 16

## Source Requirement Text
> 1. The scheduler shall [SRS017] provide an API call to install a task into a rate group. The API call is invoked during system initialization.

## Identified Patterns
- [[pat-api-invocation]]
- [[pat-lifecycle-boundary]]
- [[pat-component-interaction]]

## Relevant Concepts
- [[concept-rate-groups-tasks]]

## Relevant Formalization Notes
- [[form-api-specifications]]

## Known Dependencies
- [[req-srs196]]

## Missing Parameters & Clarification Questions
- **Missing Parameters:** Missing parameter type definitions for task pointer and rate group ID.
- **Clarification Questions:** Can tasks be uninstalled at runtime?

## Known Inconsistencies & Issues
- INC-004: Section 3.2.2.1 mixes local numbering with global-style R2/R4/R5 labels.
