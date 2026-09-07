---
id: req-srs234
srs_id: "SRS234"
global_number: 2
source_number: 2
section: "3.2.1"
page: 15
patterns:
  - "[[pat-sequential-dependency]]"
  - "[[pat-api-invocation]]"
  - "[[pat-handshake]]"
  - "[[pat-component-interaction]]"
concepts:
  - "[[concept-fcp-fcr-architecture]]"
formalization:
  - "[[form-api-specifications]]"
dependencies:
  - "[[req-srs194]]"
---

# Requirement R2 SRS234

## Metadata
- **Global Requirement Number:** R2
- **Source/Local Requirement Number:** #2
- **SRS Identifier:** SRS234
- **Section:** 3.2.1
- **Page:** 15

## Source Requirement Text
> 2. As part of System Initialization , the Boot ROM shall [SRS234] be configured to, after completing IBIT, call the manufacturer-supplied VxWorks Board Support Package (BSP) initialization software followed by a call to the FTSS System Initialization software.

## Identified Patterns
- [[pat-sequential-dependency]]
- [[pat-api-invocation]]
- [[pat-handshake]]
- [[pat-component-interaction]]

## Relevant Concepts
- [[concept-fcp-fcr-architecture]]

## Relevant Formalization Notes
- [[form-api-specifications]]

## Known Dependencies
- [[req-srs194]]

## Missing Parameters & Clarification Questions
- **Missing Parameters:** Missing explicit timeout for IBIT completion.
- **Clarification Questions:** What occurs if IBIT fails?

## Known Inconsistencies & Issues
- None identified.
