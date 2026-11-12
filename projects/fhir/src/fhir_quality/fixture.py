"""Deterministic, independently generated input with deliberately seeded defects."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from .validate import BASE_URL

FEEDS = ("Ambulatory", "Community clinic", "Virtual care")
SCENARIO_PLAN = {
    "Ambulatory": {0: "wrong_unit", 3: "outside_period", 8: "duplicate"},
    "Community clinic": {
        0: "invalid_birth_date",
        2: "period_reversed",
        4: "orphan_encounter",
        6: "unmapped_code",
        9: "wrong_unit",
        12: "outside_period",
    },
    "Virtual care": {
        0: "patient_mismatch",
        2: "missing_subject",
        4: "invalid_value",
        7: "wrong_reference_type",
        10: "observation_missing_time",
        15: "outside_period",
        19: "outside_period",
    },
}


def entries_for_batch(feed: str, batch: int) -> list[dict]:
    feed_id = FEEDS.index(feed) + 1
    day = date(2025, 1, 6) + timedelta(days=batch * 7 + feed_id)
    start, end = f"{day}T10:00:00Z", f"{day}T10:30:00Z"
    entries = []
    for index in range(24):
        key = f"{feed_id}-{batch + 1:02d}-{index:02d}"
        patient_id = f"p-{key}"
        encounter_id = f"e-{key}"
        patient_ref = source_reference("Patient", patient_id, index)
        encounter_ref = source_reference("Encounter", encounter_id, index)
        patient = {"resourceType": "Patient", "id": patient_id, "birthDate": "1982-02-17"}
        encounter = {
            "resourceType": "Encounter",
            "id": encounter_id,
            "status": "finished",
            "class": {
                "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                "code": "VR" if feed == "Virtual care" else "AMB",
            },
            "subject": {"reference": patient_ref},
            "period": {"start": start, "end": end},
        }
        pounds = (index + batch) % 3 == 0
        weight = observation(
            f"ow-{key}", patient_ref, encounter_ref, day,
            "29463-7", 132 + index if pounds else 60 + index,
            "[lb_av]" if pounds else "kg",
        )
        heart_rate = observation(
            f"oh-{key}", patient_ref, encounter_ref, day, "8867-4", 65 + index, "/min",
        )
        # The scenarios rotate across patients and do not overlap within each batch.
        scenario = SCENARIO_PLAN[feed].get((index - batch) % 24)
        if scenario == "wrong_unit":
            weight["valueQuantity"]["code"] = "cm"
        elif scenario == "outside_period":
            heart_rate["effectiveDateTime"] = f"{day}T10:45:00Z"
        elif scenario == "duplicate":
            entries.append(as_entry(weight.copy(), index))
        elif scenario == "invalid_birth_date":
            patient["birthDate"] = "1982-02-31"
        elif scenario == "period_reversed":
            encounter["period"] = {"start": end, "end": start}
        elif scenario == "orphan_encounter":
            weight["encounter"]["reference"] = source_reference("Encounter", "e-missing", index)
        elif scenario == "unmapped_code":
            weight["code"]["coding"][0]["code"] = "not-in-demo-catalog"
        elif scenario == "patient_mismatch":
            other = (index + 1) % 24
            other_id = f"p-{feed_id}-{batch + 1:02d}-{other:02d}"
            weight["subject"]["reference"] = full_url("Patient", other_id, other)
        elif scenario == "missing_subject":
            del encounter["subject"]
        elif scenario == "invalid_value":
            weight["valueQuantity"]["value"] = "not numeric"
        elif scenario == "wrong_reference_type":
            heart_rate["encounter"]["reference"] = patient_ref
        elif scenario == "observation_missing_time":
            del weight["effectiveDateTime"]
        entries.extend(as_entry(resource, index) for resource in (patient, encounter, weight, heart_rate))
    return entries


def observation(resource_id, patient_ref, encounter_ref, day, loinc, value, unit):
    return {
        "resourceType": "Observation",
        "id": resource_id,
        "status": "final",
        "code": {"coding": [{"system": "http://loinc.org", "code": loinc}]},
        "subject": {"reference": patient_ref},
        "encounter": {"reference": encounter_ref},
        "effectiveDateTime": f"{day}T10:15:00Z",
        "valueQuantity": {"value": value, "code": unit, "system": "http://unitsofmeasure.org"},
    }


def full_url(resource_type: str, resource_id: str, index: int) -> str:
    absolute = f"{BASE_URL}{resource_type}/{resource_id}"
    return absolute if index % 2 else f"urn:uuid:{uuid5(NAMESPACE_URL, absolute)}"


def source_reference(resource_type: str, resource_id: str, index: int) -> str:
    # Relative references originate only at entries whose fullUrl provides a REST base.
    return f"{resource_type}/{resource_id}" if index % 2 else full_url(resource_type, resource_id, index)


def as_entry(resource: dict, index: int) -> dict:
    identity = full_url(resource["resourceType"], resource["id"], index)
    return {"fullUrl": identity, "resource": resource}


def generate(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for feed in FEEDS:
        feed_id = FEEDS.index(feed) + 1
        for batch in range(4):
            payload = {
                "resourceType": "Bundle",
                "id": f"feed-{feed_id}-{batch + 1:02d}",
                "type": "collection",
                "entry": entries_for_batch(feed, batch),
            }
            path = directory / f"{feed_id}-{batch + 1:02d}.json"
            path.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
