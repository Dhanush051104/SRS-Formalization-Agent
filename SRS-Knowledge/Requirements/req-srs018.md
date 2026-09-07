---
id: req-srs018
srs_id: "SRS018"
global_number: 20
source_number: 3
section: "3.2.2.1"
page: 16
patterns:
  - "[[pat-api-invocation]]"
  - "[[pat-lifecycle-boundary]]"
  - "[[pat-component-interaction]]"
concepts:
  - "[[concept-rate-groups-tasks]]"
  - "[[concept-vehicle-modes]]"
formalization:
  - "[[form-api-specifications]]"
dependencies:
  - "[[req-srs197]]"
---

# Requirement R20 SRS018

## Metadata
- **Global Requirement Number:** R20
- **Source/Local Requirement Number:** #3
- **SRS Identifier:** SRS018
- **Section:** 3.2.2.1
- **Page:** 16

## Source Requirement Text
> 3. The scheduler shall [SRS018] provide an API call to install a rate group into a vehicle mode at system initialization.

## Identified Patterns
- [[pat-api-invocation]]
- [[pat-lifecycle-boundary]]
- [[pat-component-interaction]]

## Relevant Concepts
- [[concept-rate-groups-tasks]]
- [[concept-vehicle-modes]]

## Relevant Formalization Notes
- [[form-api-specifications]]

## Known Dependencies
- [[req-srs197]]

## Missing Parameters & Clarification Questions
- **Missing Parameters:** Missing parameter types for rate group and vehicle mode.
- **Clarification Questions:** Is this a structural prerequisite for R18?

## Known Inconsistencies & Issues
- None identified.
