import json

import mido

from pa800_optimizer.analysis.style_import_contract import analyze_style_import_contract
from pa800_optimizer.core.smf_preflight import preflight_smf
from tools.process_certification_midis import ALPHABET, SCHEMA, generate


def test_a_to_z_certification_suite_is_complete_and_matches_declared_outcomes(tmp_path):
    rows = generate(tmp_path / "cert")
    assert len(rows) == 52
    assert tuple(dict.fromkeys(row["stage"] for row in rows)) == ALPHABET
    assert all(sum(row["stage"] == stage for row in rows) == 2 for stage in ALPHABET)
    assert all({row["polarity"] for row in rows if row["stage"] == stage} == {"positive", "negative"}
               for stage in ALPHABET)
    assert sum(row["file"].endswith(".kar") for row in rows) == 1
    for row in rows:
        assert row["observed"]["container_pass"] == row["expected"]["container_pass"]
        assert row["observed"]["loadable"] == row["expected"]["loadable"]
        assert row["expected"]["certification_outcome"] == ("PASS" if row["polarity"] == "positive" else "REJECT")
        raw=(tmp_path/"cert"/row["file"]).read_bytes()
        assert b"PKL0" not in raw
        if row["observed"]["container_pass"]:assert b"MTrk" in raw


def test_generation_is_byte_deterministic(tmp_path):
    first = generate(tmp_path / "first")
    second = generate(tmp_path / "second")
    assert [(row["file"], row["sha256"], row["bytes"]) for row in first] == [
        (row["file"], row["sha256"], row["bytes"]) for row in second
    ]


def test_manifest_is_machine_readable_and_self_consistent(tmp_path):
    output = tmp_path / "cert"
    rows = generate(output)
    manifest = json.loads((output / "PROCESS_CERTIFICATION_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == SCHEMA
    assert manifest["serialization"] == "STANDARD_MIDI_FILE"
    assert "NOT_HARDWARE_CERTIFICATION" in manifest["scope"]
    assert manifest["scenario_count"] == len(manifest["scenarios"]) == 52
    assert manifest["scenarios"] == rows
    for row in rows:
        assert preflight_smf(output / row["file"])["pass"] == row["expected"]["container_pass"]


def test_style_contract_positive_and_negative_fixtures_are_real(tmp_path):
    output = tmp_path / "cert"
    rows = generate(output)
    styles = {(row["name"], row["polarity"]): row for row in rows if row["name"].startswith("style_")}
    strict = analyze_style_import_contract(mido.MidiFile(str(output / styles[("style_strict_contract", "positive")]["file"])))
    minimum = analyze_style_import_contract(mido.MidiFile(str(output / styles[("style_minimum_header", "positive")]["file"])))
    uppercase = analyze_style_import_contract(mido.MidiFile(str(output / styles[("style_uppercase_marker_reject", "negative")]["file"])))
    outside = analyze_style_import_contract(mido.MidiFile(str(output / styles[("style_outside_channel_reject", "negative")]["file"])))
    unsupported = analyze_style_import_contract(mido.MidiFile(str(output / styles[("style_unsupported_cc_reject", "negative")]["file"])))
    assert strict["strict_export_contract"]
    assert minimum["minimum_importable"] and not minimum["strict_export_contract"]
    assert not uppercase["minimum_importable"]
    assert outside["outside_style_channel_count"] > 0
    assert unsupported["unsupported_event_count"] > 0


def test_semantic_negative_files_remain_loadable_for_downstream_rejection(tmp_path):
    output = tmp_path / "cert"
    rows = generate(output)
    for name in ("dnc_cross_channel_negative", "unmatched_note_negative"):
        row = next(row for row in rows if row["name"] == name and row["polarity"] == "negative")
        assert row["expected"]["container_pass"] and row["expected"]["loadable"]
        assert mido.MidiFile(str(output / row["file"])).tracks