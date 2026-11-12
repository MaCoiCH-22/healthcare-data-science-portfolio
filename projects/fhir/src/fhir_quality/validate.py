"""Closed-bundle QA rules for a deliberately bounded FHIR R4 ingest contract."""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import UUID

BASE_URL = "https://synthetic.example.invalid/fhir/"
RULES = {
    "RESOURCE_SHAPE": ("Resource shape", "error", "Structure"),
    "IDENTITY": ("Invalid local identity", "error", "Structure"),
    "DUPLICATE": ("Duplicate identity", "error", "Structure"),
    "STATUS": ("Unsupported status", "error", "Structure"),
    "UNSUPPORTED_SEMANTICS": ("Unsupported modifying content", "error", "Structure"),
    "ENCOUNTER_CLASS": ("Unsupported encounter class", "error", "Terminology"),
    "BIRTH_DATE": ("Invalid or missing birth date", "error", "Time"),
    "PERIOD": ("Invalid or missing encounter period", "error", "Time"),
    "EFFECTIVE_TIME": ("Invalid or missing observation time", "error", "Time"),
    "REF_FORMAT": ("Reference missing or wrong target type", "error", "References"),
    "REF_UNRESOLVED": ("Reference missing from bundle or ambiguous", "error", "References"),
    "SUBJECT_MISMATCH": ("Observation and encounter subjects differ", "error", "References"),
    "LOINC": ("LOINC code unmapped or ambiguous", "error", "Terminology"),
    "QUANTITY": ("Invalid or missing numeric quantity", "error", "Terminology"),
    "UCUM": ("UCUM unit incompatible with code", "error", "Terminology"),
    "OUTSIDE_PERIOD": ("Observation outside encounter period", "warning", "Time"),
    "DEPENDENCY": ("Referenced resource is quarantined", "error", "References"),
}
SUPPORTED_TYPES = ("Patient", "Encounter", "Observation")
ENCOUNTER_STATUS = {
    "planned", "arrived", "triaged", "in-progress", "onleave",
    "finished", "cancelled", "entered-in-error", "unknown",
}
OBSERVATION_STATUS = {
    "final", "amended", "corrected",
}
ALTERNATE_EFFECTIVE = {"effectivePeriod", "effectiveTiming", "effectiveInstant"}
ALTERNATE_VALUES = {
    "valueCodeableConcept", "valueString", "valueBoolean", "valueInteger", "valueRange", "valueRatio",
    "valueSampledData", "valueTime", "valueDateTime", "valuePeriod", "dataAbsentReason",
}
ENCOUNTER_CLASS_SYSTEM = "http://terminology.hl7.org/CodeSystem/v3-ActCode"
LOINC_SYSTEM = "http://loinc.org"
UCUM_SYSTEM = "http://unitsofmeasure.org"
# Each code maps to an output unit and accepted input codes with scale factors.
MEASURES = {
    "29463-7": ("kg", {"kg": 1, "[lb_av]": 0.45359237, "g": 0.001}),
    "8302-2": ("cm", {"cm": 1, "m": 100, "[in_i]": 2.54}),
    "8867-4": ("/min", {"/min": 1}),
}
FHIR_ID = re.compile(r"[A-Za-z0-9.-]{1,64}\Z")
FULL_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
ZONED_TIME = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?"
    r"(?:Z|[+-](?:0\d|1[0-3]):[0-5]\d|[+-]14:00)\Z"
)


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str

    @property
    def severity(self) -> str:
        return RULES[self.rule][1]


@dataclass
class Record:
    entry_index: int
    entry: dict
    resource: dict
    content_hash: str
    findings: list[Finding] = field(default_factory=list)
    targets: dict[str, int] = field(default_factory=dict)
    start: datetime | None = None
    end: datetime | None = None
    normalized: tuple[str, float, str] | None = None

    @property
    def resource_type(self):
        return self.resource.get("resourceType")

    @property
    def resource_id(self):
        return self.resource.get("id")

    @property
    def full_url(self):
        return self.entry.get("fullUrl")

    @property
    def direct_error(self) -> bool:
        return any(item.severity == "error" and item.rule != "DEPENDENCY" for item in self.findings)

    @property
    def quarantined(self) -> bool:
        return any(item.severity == "error" for item in self.findings)

    def flag(self, rule: str, path: str = "") -> None:
        self.findings.append(Finding(rule, f"entry[{self.entry_index}].resource{path}"))


def dictionary(value) -> dict:
    return value if isinstance(value, dict) else {}


def string_in(value, options) -> bool:
    return isinstance(value, str) and value in options


def valid_id(value) -> bool:
    return isinstance(value, str) and bool(FHIR_ID.fullmatch(value))


def valid_full_url(value) -> bool:
    if not isinstance(value, str):
        return False
    if value.startswith(BASE_URL):
        resource_type, _, resource_id = value.removeprefix(BASE_URL).partition("/")
        return resource_type in SUPPORTED_TYPES and valid_id(resource_id)
    if not value.startswith("urn:uuid:"):
        return False
    try:
        return value == f"urn:uuid:{UUID(value[9:])}"
    except ValueError:
        return False


def parse_time(value) -> datetime | None:
    if not isinstance(value, str) or not ZONED_TIME.fullmatch(value):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def parse_birth_date(value) -> date | None:
    if not isinstance(value, str) or not FULL_DATE.fullmatch(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def canonical_hash(value) -> str:
    canonical = json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def has_modifier(value) -> bool:
    if isinstance(value, dict):
        return "modifierExtension" in value or any(has_modifier(child) for child in value.values())
    if isinstance(value, list):
        return any(has_modifier(child) for child in value)
    return False


def scan_entries(entries: list) -> tuple[list[Record], dict[str, list[int]]]:
    index = defaultdict(list)
    records = []
    for position, raw in enumerate(entries):
        entry = dictionary(raw)
        resource = dictionary(entry.get("resource"))
        record = Record(position, entry, resource, canonical_hash(raw))
        records.append(record)
        if "implicitRules" in resource or has_modifier(entry):
            record.flag("UNSUPPORTED_SEMANTICS")
        if not string_in(record.resource_type, SUPPORTED_TYPES):
            record.flag("RESOURCE_SHAPE")
        if not valid_id(record.resource_id):
            record.flag("IDENTITY", ".id")
        elif string_in(record.resource_type, SUPPORTED_TYPES):
            index[f"{record.resource_type}/{record.resource_id}"].append(position)
        if valid_full_url(record.full_url) and (
            not record.full_url.startswith(BASE_URL)
            or record.full_url == f"{BASE_URL}{record.resource_type}/{record.resource_id}"
        ):
            index[record.full_url].append(position)
        else:
            record.findings.append(Finding("IDENTITY", f"entry[{position}].fullUrl"))

    # One finding per duplicated identity field. All colliding entries are quarantined.
    for identity, positions in index.items():
        if len(positions) > 1:
            for position in positions:
                if valid_full_url(identity):
                    records[position].findings.append(Finding("DUPLICATE", f"entry[{position}].fullUrl"))
                else:
                    records[position].flag("DUPLICATE", ".id")
    return records, index


def resolve(record: Record, records: list[Record], index: dict, field: str, target: str) -> None:
    raw = dictionary(record.resource.get(field)).get("reference")
    path = f".{field}.reference"
    if not isinstance(raw, str):
        record.flag("REF_FORMAT", path)
        return
    if valid_full_url(raw):
        lookup = raw
    else:
        resource_type, _, resource_id = raw.partition("/")
        if (resource_type != target or not valid_id(resource_id)
                or not isinstance(record.full_url, str) or not record.full_url.startswith(BASE_URL)):
            record.flag("REF_FORMAT", path)
            return
        lookup = f"{BASE_URL}{raw}"
    candidates = index.get(lookup, [])
    if len(candidates) != 1:
        record.flag("REF_UNRESOLVED", path)
        return
    destination = candidates[0]
    if records[destination].resource_type != target:
        record.flag("REF_FORMAT", path)
        return
    record.targets[field] = destination


def check_encounter(record: Record) -> None:
    resource = record.resource
    if not string_in(resource.get("status"), ENCOUNTER_STATUS) or resource["status"] == "entered-in-error":
        record.flag("STATUS", ".status")
    coding = dictionary(resource.get("class"))
    if coding.get("system") != ENCOUNTER_CLASS_SYSTEM or not string_in(
        coding.get("code"), ("AMB", "EMER", "IMP", "VR"),
    ):
        record.flag("ENCOUNTER_CLASS", ".class")
    period = dictionary(resource.get("period"))
    record.start = parse_time(period.get("start"))
    record.end = parse_time(period.get("end"))
    if record.start is None or record.end is None or record.start > record.end:
        record.flag("PERIOD", ".period")
        record.start = record.end = None


def number(value) -> bool:
    # Check the actual number type first to reject bools and huge ints without overflow.
    return type(value) in (int, float) and abs(value) <= 1e100 and math.isfinite(value)


def check_observation(record: Record, records: list[Record]) -> None:
    resource = record.resource
    if not string_in(resource.get("status"), OBSERVATION_STATUS):
        record.flag("STATUS", ".status")
    timestamp = parse_time(resource.get("effectiveDateTime"))
    if timestamp is None or ALTERNATE_EFFECTIVE.intersection(resource):
        record.flag("EFFECTIVE_TIME", ".effectiveDateTime")
        timestamp = None
    if "encounter" in record.targets:
        encounter = records[record.targets["encounter"]]
        own_patient, encounter_patient = record.targets.get("subject"), encounter.targets.get("subject")
        if own_patient is not None and encounter_patient is not None and own_patient != encounter_patient:
            record.flag("SUBJECT_MISMATCH", ".subject")
        if timestamp is not None and encounter.start is not None and encounter.end is not None:
            if not encounter.start <= timestamp <= encounter.end:
                record.flag("OUTSIDE_PERIOD", ".effectiveDateTime")

    codings = dictionary(resource.get("code")).get("coding")
    candidates = [
        coding.get("code") for coding in codings
        if isinstance(coding, dict) and coding.get("system") == LOINC_SYSTEM
    ] if isinstance(codings, list) else []
    measure = MEASURES[candidates[0]] if len(candidates) == 1 and string_in(candidates[0], MEASURES) else None
    if measure is None:
        record.flag("LOINC", ".code.coding")
    quantity = dictionary(resource.get("valueQuantity"))
    value = quantity.get("value")
    # A comparator is an inequality, so coercing it to a point value loses information.
    valid_quantity = (number(value) and "comparator" not in quantity
                      and not ALTERNATE_VALUES.intersection(resource) and "component" not in resource)
    if not valid_quantity:
        record.flag("QUANTITY", ".valueQuantity")
    if measure is not None:
        unit, factors = measure
        source_unit = quantity.get("code")
        if quantity.get("system") != UCUM_SYSTEM or not string_in(source_unit, factors):
            record.flag("UCUM", ".valueQuantity.code")
        elif valid_quantity:
            record.normalized = (candidates[0], float(value) * factors[source_unit], unit)


def audit(entries: list) -> list[Record]:
    records, index = scan_entries(entries)
    for record in records:
        if record.resource_type == "Patient":
            if parse_birth_date(record.resource.get("birthDate")) is None:
                record.flag("BIRTH_DATE", ".birthDate")
        if record.resource_type == "Encounter":
            resolve(record, records, index, "subject", "Patient")
            check_encounter(record)

    for record in records:
        if record.resource_type == "Observation":
            resolve(record, records, index, "subject", "Patient")
            resolve(record, records, index, "encounter", "Encounter")
            check_observation(record, records)

    # Patients are terminal targets. Evaluate encounters before observations so that
    # the complete Patient → Encounter → Observation dependency path is covered.
    for resource_type in ("Encounter", "Observation"):
        for record in records:
            if record.resource_type == resource_type:
                for name, target in record.targets.items():
                    if records[target].quarantined:
                        record.flag("DEPENDENCY", f".{name}.reference")
    return records
