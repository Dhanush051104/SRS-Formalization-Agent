---
id: req-srs189
srs_id: "SRS189"
global_number: 14
source_number: 14
section: "3.2.1"
page: 16
patterns:
  - "[[pat-bounded-waiting]]"
  - "[[pat-timeout-deadline]]"
  - "[[pat-handshake]]"
  - "[[pat-graceful-degradation]]"
concepts:
  - "[[concept-icp-handshake]]"
formalization:
  - "[[form-timed-ltl-rules]]"
  - "[[form-fault-recovery]]"
dependencies:
  - "[[req-srs221]]"
  - "[[req-srs243]]"
---

# Requirement R14 SRS189

## Metadata
- **Global Requirement Number:** R14
- **Source/Local Requirement Number:** #14
- **SRS Identifier:** SRS189
- **Section:** 3.2.1
- **Page:** 16

## Source Requirement Text
> 14. The FCP shall [SRS189] wait up to 2.5 seconds (from the sending of the FCP Ready Sync) for the ICP Ready signal. Note that FTSS will not fail the FCR if this signal is not received within this time. FTSS will wait until the normal ICP presence test fails.

## Identified Patterns
- [[pat-bounded-waiting]]
- [[pat-timeout-deadline]]
- [[pat-handshake]]
- [[pat-graceful-degradation]]

## Relevant Concepts
- [[concept-icp-handshake]]

## Relevant Formalization Notes
- [[form-timed-ltl-rules]]
- [[form-fault-recovery]]

## Known Dependencies
- [[req-srs221]]
- [[req-srs243]]

## Missing Parameters & Clarification Questions
- **Missing Parameters:** Missing boundary/timing of normal ICP presence test.
- **Clarification Questions:** When does presence test execute?

## Known Inconsistencies & Issues
- None identified.
