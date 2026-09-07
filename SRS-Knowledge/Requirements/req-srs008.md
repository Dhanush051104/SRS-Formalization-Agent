---
id: req-srs008
srs_id: "SRS008"
global_number: 5
source_number: 5
section: "3.2.1"
page: 15
patterns:
  - "[[pat-bounded-waiting]]"
  - "[[pat-derived-math-constraint]]"
  - "[[pat-component-interaction]]"
concepts:
  - "[[concept-fcp-fcr-architecture]]"
formalization:
  - "[[form-timed-ltl-rules]]"
  - "[[form-metric-derivations]]"
dependencies:
  - "[[req-srs010]]"
---

# Requirement R5 SRS008

## Metadata
- **Global Requirement Number:** R5
- **Source/Local Requirement Number:** #5
- **SRS Identifier:** SRS008
- **Section:** 3.2.1
- **Page:** 15

## Source Requirement Text
> 5. System Initialization shall [SRS008] synchronize the FCP virtual group in the presence of a power on skew of 2.5 seconds.

## Identified Patterns
- [[pat-bounded-waiting]]
- [[pat-derived-math-constraint]]
- [[pat-component-interaction]]

## Relevant Concepts
- [[concept-fcp-fcr-architecture]]

## Relevant Formalization Notes
- [[form-timed-ltl-rules]]
- [[form-metric-derivations]]

## Known Dependencies
- [[req-srs010]]

## Missing Parameters & Clarification Questions
- **Missing Parameters:** Missing explicit synchronization completion deadline.
- **Clarification Questions:** Is pairwise maximum skew inferred to be 2.5 seconds?

## Known Inconsistencies & Issues
- None identified.
