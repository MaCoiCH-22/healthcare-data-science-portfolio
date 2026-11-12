# Methods and data contract

## Input and synthetic fixture

The generator emits four batches per synthetic feed, with 24 synthetic patients per batch. Each begins with one Encounter and two Observations per patient. The generator uses deterministic IDs and dates and rotates seeded cases among source records. One repeated Observation per ambulatory batch brings the entry count from 1,152 to 1,156. An input entry is the denominator, so both entries in each duplicate pair are counted. A finding is one rule on one entry and field path. The fixture uses plain synthetic identifiers, invented values, and the reserved `example.invalid` domain.

The CLI expects UTF-8 JSON files named `1-01.json` through `3-04.json` for the default fixture. A matching `Bundle.id` is derived from the filename. A run can accept a subset of fixture batches, with feed identity derived from the filename. The input folder should contain only JSON in this format. JSON duplicate object keys, non-finite numbers, and malformed bundle envelopes fail the run. Unsupported or malformed entries inside valid envelopes remain in the denominator and enter quarantine.

## Resource contract

- `Patient` needs a valid local identity and a complete birth date. Birth date can be optional or less precise under broader FHIR rules.
- `Encounter` needs a known R4 status other than `entered-in-error`, one of four selected encounter class codes, a Patient subject, and ordered start and end timestamps. Other valid FHIR encounter classes and subjects are outside the demo policy.
- `Observation` accepts `final`, `amended` and `corrected` for analytical use. It requires a Patient subject, an Encounter reference, one zoned `effectiveDateTime`, a supported scalar `valueQuantity` and one recognized LOINC coding. It excludes component observations, numeric comparators, and alternative value and effective-time forms. Out-of-period observations receive a warning.
- Time comparisons use timezone-aware timestamps. Dates are full calendar days and time precision is up to microseconds. Leap seconds, partial dates, and absent end times fall outside this contract.
- References are literal, local to the collection and resolved without network access. Supported forms are exact UUID URNs, exact absolute URLs under the synthetic REST base, and relative `Type/id` references resolved from source entries with that base. URL-based identities must agree with `resourceType` and `id`. Colliding full URLs or logical `Type/id` identities quarantine every matching entry. Version-specific, identifier-only, contained, and external references fall outside the contract. The validator follows only the three explicit graph edges. It rejects implicit resource rules and modifying extensions rather than interpreting them.
- A candidate measure must be finite with an absolute magnitude no larger than `1e100` and use a listed UCUM system and code for the measurement. This numerical bound is an engineering rule for safe normalization. The engine does not set clinical value ranges or interpret individual measurements.

| LOINC | Measure | Supported UCUM input | Normalized UCUM output |
| --- | --- | --- | --- |
| 29463-7 | Body weight | `kg`, `g`, `[lb_av]` | `kg` |
| 8302-2 | Body height | `cm`, `m`, `[in_i]` | `cm` |
| 8867-4 | Heart rate | `/min` | `/min` |

Height is a supported input verified in tests. The default fixture generates weight and heart-rate measurements. A normalized row enters the ledger only when its Observation remains accepted. Aggregate means summarize artificial values and have no clinical interpretation.

## Disposition and lineage

- **Accepted** means none of the implemented rules or dependency checks produced an error. Warning-only entries remain accepted for review.
- **Direct** means the entry failed one or more local checks, including a missing, malformed, ambiguous or incompatible reference. It can also have dependency findings.
- **Dependent** means local checks passed and at least one referenced target is quarantined. One entry can receive findings on both its Patient and Encounter edges, so 36 dependency findings are consistent with 28 dependency-only entries.

For each batch, the ledger records the SHA-256 of the exact input bytes. For each entry it records a hash of a deterministic key-sorted JSON serialization plus its zero-based location. Rule findings store a source path. Resolved edges link entry offsets within the same batch. The hash and path provide traceability to a retained synthetic source file.

SQLite is the authoritative ledger for a run and enforces references among its tables. An invalid input leaves prior outputs available. The ledger and report each replace their predecessor by a separate file rename after both have been generated. Run only one writer per output directory and publish the two files together as a matched snapshot. Use separate output directories to run independent jobs concurrently.

## Validation and design decisions

The default fixture measures rule behavior on seeded cases. It cannot estimate production defect rates, precision, recall, or clinical safety. Cross-feed matching, conformance profiles, FHIRPath, additional terminology systems, workflow integration, live data, and version-specific references are future work. A staged rollout could compare rule decisions against a reviewer-labeled sample, record false positives and pipeline latency, establish a queue owner and escalation threshold for each warning, and route unsupported inputs to a formal validator. The ingest CLI is an offline research demonstration for synthetic data.

Python’s standard library minimizes setup for deterministic parsing and rules. SQLite supports foreign keys and audit queries with a single-file ledger. A browser receives aggregates; reviewer SQL remains available locally. Machine learning would add no value to these deterministic contract rules.

## Primary references

- HL7 FHIR R4 Bundle and reference resolution. [Bundle](https://hl7.org/fhir/R4/bundle.html) · [References](https://hl7.org/fhir/R4/references.html)
- HL7 FHIR R4 resource definitions and status. [Patient](https://hl7.org/fhir/R4/patient.html) · [Encounter](https://hl7.org/fhir/R4/encounter.html) · [Observation](https://hl7.org/fhir/R4/observation.html) · [Observation status](https://hl7.org/fhir/R4/codesystem-observation-status.html)
- HL7 FHIR R4 primitives, modifying extensions and validation guidance. [Data types](https://hl7.org/fhir/R4/datatypes.html) · [Extensibility](https://hl7.org/fhir/R4/extensibility.html) · [Validation](https://hl7.org/fhir/R4/validation.html)
- Regenstrief LOINC terms and the UCUM specification. [Weight](https://loinc.org/29463-7) · [Height](https://loinc.org/8302-2) · [Heart rate](https://loinc.org/8867-4) · [UCUM](https://ucum.org/ucum)
