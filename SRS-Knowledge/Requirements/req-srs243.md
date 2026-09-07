---
id: req-srs243
srs_id: "SRS243"
global_number: 15
source_number: 15
section: "3.2.1"
page: 16
patterns:
  - "[[pat-failure-handling]]"
  - "[[pat-graceful-degradation]]"
  - "[[pat-conditional-behavior]]"
  - "[[pat-component-interaction]]"
concepts:
  - "[[concept-vmebus-ne-subsystem]]"
formalization:
  - "[[form-fault-recovery]]"
dependencies:
  - "[[req-srs189]]"
  - "[[req-srs199]]"
---

# Requirement R15 SRS243

## Metadata
- **Global Requirement Number:** R15
- **Source/Local Requirement Number:** #15
- **SRS Identifier:** SRS243
- **Section:** 3.2.1
- **Page:** 16

## Source Requirement Text
> 15. The FCP shall [SRS243], if the NEFU ICP fails to send its ICP Ready signal, mask out that ICP, but continue to use the NE.

## Identified Patterns
- [[pat-failure-handling]]
- [[pat-graceful-degradation]]
- [[pat-conditional-behavior]]
- [[pat-component-interaction]]

## Relevant Concepts
- [[concept-vmebus-ne-subsystem]]

## Relevant Formalization Notes
- [[form-fault-recovery]]

## Known Dependencies
- Source Dependency: [[req-srs189]]
- Derived Dependency: [[req-srs199]] (Derived from the analyzed initialization/recovery sequence; not explicitly stated as a dependency in the source requirement.)

## Missing Parameters & Clarification Questions
- **Missing Parameters:** Missing unmask / recovery behavior specification.
- **Clarification Questions:** Can a masked ICP be re-enabled without reboot?

## Known Inconsistencies & Issues
- INC-003: R16 'other activities' list omits R15/SRS243.
