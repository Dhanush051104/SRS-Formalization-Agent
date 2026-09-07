---
id: req-srs297
srs_id: "SRS297"
global_number: 11
source_number: 11
section: "3.2.1"
page: 15
patterns:
  - "[[pat-bounded-waiting]]"
  - "[[pat-timeout-deadline]]"
  - "[[pat-handshake]]"
  - "[[pat-component-interaction]]"
concepts:
  - "[[concept-icp-handshake]]"
formalization:
  - "[[form-timed-ltl-rules]]"
dependencies:
  - "[[req-srs296]]"
---

# Requirement R11 SRS297

## Metadata
- **Global Requirement Number:** R11
- **Source/Local Requirement Number:** #11
- **SRS Identifier:** SRS297
- **Section:** 3.2.1
- **Page:** 15

## Source Requirement Text
> 11. The FCP shall [SRS297] wait up to 15 seconds, after configuring the ICP virtual groups, for communication to start from the ICP. The application can use this time on the ICP to initialize I/O boards.

## Identified Patterns
- [[pat-bounded-waiting]]
- [[pat-timeout-deadline]]
- [[pat-handshake]]
- [[pat-component-interaction]]

## Relevant Concepts
- [[concept-icp-handshake]]

## Relevant Formalization Notes
- [[form-timed-ltl-rules]]

## Known Dependencies
- [[req-srs296]]

## Missing Parameters & Clarification Questions
- **Missing Parameters:** No explicit timeout action if communication fails to start within 15s.
- **Clarification Questions:** Is sentence 2 purely informative?

## Known Inconsistencies & Issues
- None identified.
