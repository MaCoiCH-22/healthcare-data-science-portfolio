import hashlib
import json
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from src.fhir_quality.fixture import as_entry, generate, observation, source_reference
from src.fhir_quality.pipeline import DB_NAME, REPORT_NAME, validate_directory
from src.fhir_quality.validate import BASE_URL, RULES, audit, parse_time


def case(index=1):
    patient = {"resourceType": "Patient", "id": "p-1", "birthDate": "1982-02-17"}
    patient_ref = source_reference("Patient", "p-1", index)
    encounter = {
        "resourceType": "Encounter", "id": "e-1", "status": "finished",
        "subject": {"reference": patient_ref},
        "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB"},
        "period": {"start": "2025-01-08T10:00:00Z", "end": "2025-01-08T10:30:00Z"},
    }
    measure = observation(
        "o-1", patient_ref, source_reference("Encounter", "e-1", index),
        "2025-01-08", "29463-7", 132, "[lb_av]",
    )
    return [as_entry(resource, index) for resource in (patient, encounter, measure)]


def findings(record):
    return {finding.rule for finding in record.findings}


class RuleTests(unittest.TestCase):
    def test_relative_and_urn_reference_resolution_is_independent_of_entry_order(self):
        for mode in (0, 1):
            with self.subTest(mode=mode):
                observation, encounter, patient = audit(case(mode)[::-1])
                self.assertEqual(observation.targets, {"subject": 2, "encounter": 1})
                self.assertEqual(encounter.targets, {"subject": 2})
                self.assertEqual(patient.targets, {})
                self.assertFalse(any(record.quarantined for record in (observation, encounter, patient)))

    def test_quarantine_closure_when_referenced_patient_is_invalid(self):
        entries = case()
        entries[0]["resource"]["birthDate"] = "1982-02-31"
        patient, encounter, measure = audit(entries)
        self.assertEqual(findings(patient), {"BIRTH_DATE"})
        self.assertEqual(findings(encounter), {"DEPENDENCY"})
        self.assertEqual([item.rule for item in measure.findings], ["DEPENDENCY", "DEPENDENCY"])
        self.assertTrue(patient.direct_error and encounter.quarantined and measure.quarantined)
        self.assertFalse(encounter.direct_error or measure.direct_error)

    def test_wrong_type_uuid_is_rejected_and_dangling_relative_target_is_flagged(self):
        entries = case(0)
        entries[2]["resource"]["encounter"]["reference"] = entries[0]["fullUrl"]
        self.assertEqual(findings(audit(entries)[2]), {"REF_FORMAT"})
        entries = case()
        entries[2]["resource"]["encounter"]["reference"] = "Encounter/e-missing"
        self.assertEqual(findings(audit(entries)[2]), {"REF_UNRESOLVED"})

    def test_relative_reference_requires_source_with_known_rest_base(self):
        entries = case(0)
        entries[2]["resource"]["subject"]["reference"] = "Patient/p-1"
        self.assertIn("REF_FORMAT", findings(audit(entries)[2]))

    def test_duplicate_identity_quarantines_all_collisions_and_unresolved_source(self):
        entries = case()
        entries.append(as_entry(entries[0]["resource"].copy(), 1))
        first, encounter, measure, last = audit(entries)
        self.assertEqual([f.rule for f in first.findings], ["DUPLICATE", "DUPLICATE"])
        self.assertEqual(findings(last), {"DUPLICATE"})
        self.assertEqual(findings(encounter), {"REF_UNRESOLVED"})
        self.assertEqual(findings(measure), {"REF_UNRESOLVED", "DEPENDENCY"})

    def test_cross_patient_observation_detected_with_all_refs_resolved(self):
        entries = case()
        second = {"resourceType": "Patient", "id": "p-2", "birthDate": "1985-12-31"}
        entries.append(as_entry(second, 1))
        entries[2]["resource"]["subject"]["reference"] = f"{BASE_URL}Patient/p-2"
        self.assertEqual(findings(audit(entries)[2]), {"SUBJECT_MISMATCH"})

    def test_outside_period_is_warning_and_time_offsets_are_comparable(self):
        entries = case()
        measure = entries[2]["resource"]
        measure["effectiveDateTime"] = "2025-01-08T05:15:00-05:00"
        self.assertFalse(audit(entries)[2].findings)
        measure["effectiveDateTime"] = "2025-01-08T05:31:00-05:00"
        result = audit(entries)[2]
        self.assertEqual(findings(result), {"OUTSIDE_PERIOD"})
        self.assertFalse(result.quarantined)
        for value in ("2025-02-31T10:00:00Z", "2025-01-08T10:00:00", "2025-01-08T10:00:00+14:01"):
            self.assertIsNone(parse_time(value))

    def test_ucum_values_are_converted_and_ambiguous_codes_are_blocked(self):
        entries = case()
        measure = entries[2]["resource"]
        code, weight, unit = audit(entries)[2].normalized
        self.assertEqual((code, unit), ("29463-7", "kg"))
        self.assertAlmostEqual(weight, 59.87419284)
        measure["code"]["coding"] = [{"system": "http://loinc.org", "code": "8302-2"}]
        measure["valueQuantity"].update(code="[in_i]", value=68)
        self.assertAlmostEqual(audit(entries)[2].normalized[1], 172.72)
        measure["code"]["coding"] *= 2
        self.assertEqual(findings(audit(entries)[2]), {"LOINC"})

    def test_quantity_requires_scalar_without_competing_choice_or_comparator(self):
        for bad in (False, "40", {"count": 2}, 10**150):
            with self.subTest(bad=bad):
                entries = case()
                entries[2]["resource"]["valueQuantity"]["value"] = bad
                self.assertIn("QUANTITY", findings(audit(entries)[2]))
        entries = case()
        entries[2]["resource"].update(valueString="132", effectivePeriod={"start": "2025-01-08"})
        self.assertEqual(findings(audit(entries)[2]), {"EFFECTIVE_TIME", "QUANTITY"})
        entries = case()
        entries[2]["resource"]["valueQuantity"]["comparator"] = ">"
        self.assertEqual(findings(audit(entries)[2]), {"QUANTITY"})

    def test_modifier_and_non_finalized_observation_do_not_enter_analysis(self):
        entries = case()
        entries[0]["resource"]["name"] = [{"modifierExtension": [{"url": "https://example.invalid/mod"}]}]
        entries[2]["resource"]["status"] = "entered-in-error"
        patient, encounter, measure = audit(entries)
        self.assertEqual(findings(patient), {"UNSUPPORTED_SEMANTICS"})
        self.assertEqual(findings(encounter), {"DEPENDENCY"})
        self.assertEqual(findings(measure), {"STATUS", "DEPENDENCY"})

    def test_malformed_entry_is_counted_and_quarantined(self):
        entries = case()
        entries.extend([False, {"resource": {"resourceType": [], "id": {"foo": "bar"}}}])
        first, second = audit(entries)[-2:]
        self.assertEqual(findings(first), {"RESOURCE_SHAPE", "IDENTITY"})
        self.assertEqual(findings(second), {"RESOURCE_SHAPE", "IDENTITY"})

    def test_encounter_period_reversed_and_unsupported_class_are_direct_errors(self):
        entries = case()
        encounter = entries[1]["resource"]
        encounter["class"]["code"] = "OUT-OF-SCOPE"
        encounter["period"] = {"start": "2025-01-08T11:00:00Z", "end": "2025-01-08T10:00:00Z"}
        self.assertEqual(findings(audit(entries)[1]), {"PERIOD", "ENCOUNTER_CLASS"})


class PipelineTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source"
        self.output = self.root / "output"
        generate(self.source)

    def test_fixture_regeneration_and_report_are_byte_reproducible(self):
        copy = self.root / "copy"
        generate(copy)
        for first in self.source.glob("*.json"):
            self.assertEqual(first.read_bytes(), (copy / first.name).read_bytes())
        second_output = self.root / "output-copy"
        validate_directory(self.source, self.output)
        validate_directory(copy, second_output)
        self.assertEqual((self.output / REPORT_NAME).read_bytes(), (second_output / REPORT_NAME).read_bytes())

    def test_fixture_counts_reconcile_across_resources_rules_and_feeds(self):
        report = validate_directory(self.source, self.output)
        summary = report["summary"]
        self.assertEqual(summary, {
            "batches": 12, "resources": 1156, "accepted": 1076, "quarantined": 80,
            "direct_quarantine": 52, "dependent_quarantine": 28, "findings": 112,
            "errors": 96, "warnings": 16, "accepted_measurements": 516,
        })
        self.assertEqual(len(report["rules"]), len(RULES))
        self.assertEqual(summary["findings"], sum(rule["count"] for rule in report["rules"]))
        self.assertEqual(summary["findings"], sum(rule["count"] for rule in report["feed_rules"]))
        self.assertEqual(summary["resources"], sum(feed["resources"] for feed in report["feeds"]))
        self.assertEqual(summary["quarantined"], sum(feed["quarantined"] for feed in report["feeds"]))
        self.assertEqual(summary["accepted_measurements"], sum(item["count"] for item in report["measures"]))

    def test_sqlite_lineage_matches_bytes_and_accepted_resources_have_no_bad_dependencies(self):
        validate_directory(self.source, self.output)
        with closing(sqlite3.connect(self.output / DB_NAME)) as connection:
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
            batch, source, digest = connection.execute(
                "SELECT batch_id, source_file, sha256 FROM batch ORDER BY source_file LIMIT 1"
            ).fetchone()
            self.assertEqual(digest, hashlib.sha256((self.source / source).read_bytes()).hexdigest())
            self.assertEqual(batch, "feed-1-01")
            problematic = connection.execute("""
                SELECT COUNT(*) FROM reference AS edge
                JOIN resource AS src
                  ON src.batch_id = edge.batch_id AND src.entry_index = edge.entry_index
                JOIN resource AS dest
                  ON dest.batch_id = edge.batch_id AND dest.entry_index = edge.target_index
                WHERE src.disposition = 'accepted' AND dest.disposition <> 'accepted'
            """).fetchone()[0]
            self.assertEqual(problematic, 0)
            warnings_still_accepted = connection.execute("""
                SELECT COUNT(*) FROM finding JOIN resource USING (batch_id, entry_index)
                WHERE rule_id = 'OUTSIDE_PERIOD' AND disposition = 'accepted'
            """).fetchone()[0]
            self.assertEqual(warnings_still_accepted, 16)

    def test_bad_batch_does_not_replace_existing_output(self):
        validate_directory(self.source, self.output)
        before = {name: (self.output / name).read_bytes() for name in (DB_NAME, REPORT_NAME)}
        (self.source / "3-04.json").write_text('{"entry": 1, "entry": []}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate JSON"):
            validate_directory(self.source, self.output)
        self.assertEqual({name: (self.output / name).read_bytes() for name in before}, before)

    def test_nonfinite_number_and_invalid_envelope_are_rejected(self):
        batch = self.source / "1-01.json"
        batch.write_text('{"entry": [1e999]}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "non-finite JSON"):
            validate_directory(self.source, self.output)
        batch.write_text(json.dumps({"resourceType": "Bundle", "entry": []}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "matching collection Bundle"):
            validate_directory(self.source, self.output)
        self.assertFalse((self.output / REPORT_NAME).exists())


if __name__ == "__main__":
    unittest.main()
