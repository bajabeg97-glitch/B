"""Generate deterministic A-Z process-certification MIDI/KAR fixtures.

The suite intentionally contains both successful pipeline inputs and negative
fixtures.  Negative fixtures are split into readable MIDI files with an
invalid musical/device contract and byte-level SMF container corruption.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

import mido

from pa800_optimizer.analysis.style_import_contract import analyze_style_import_contract
from pa800_optimizer.core.smf_preflight import preflight_smf


SCHEMA = "PA800_PROCESS_COVERAGE_MIDI_V2"
ALPHABET = tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def _message(kind, time=0, **kwargs):
    cls = mido.MetaMessage if kind in {
        "track_name", "marker", "time_signature", "set_tempo", "lyrics", "text",
    } else mido.Message
    return cls(kind, time=time, **kwargs)


def _mid(tracks, *, midi_type=1, ticks=192):
    mid = mido.MidiFile(type=midi_type, ticks_per_beat=ticks)
    for events in tracks:
        track = mido.MidiTrack()
        track.extend(events)
        mid.tracks.append(track)
    return mid


def _note(channel, pitch, velocity=80, duration=96, delay=0):
    return [
        _message("note_on", channel=channel, note=pitch, velocity=velocity, time=delay),
        _message("note_off", channel=channel, note=pitch, velocity=0, time=duration),
    ]


def _identity(channel, msb=121, lsb=0, program=0):
    return [
        _message("control_change", channel=channel, control=0, value=msb),
        _message("control_change", channel=channel, control=32, value=lsb),
        _message("program_change", channel=channel, program=program),
    ]


def _style(strict=True, marker="v1cv1", channel=8, unsupported_cc=None):
    events = [
        _message("marker", text=marker),
        _message("time_signature", numerator=4, denominator=4),
    ]
    if strict:
        events += _identity(channel, 121, 13, 33)
        events.append(_message("control_change", channel=channel, control=11, value=100))
    if unsupported_cc is not None:
        events.append(_message("control_change", channel=channel, control=unsupported_cc, value=64))
    events += _note(channel, 40, 80)
    return _mid([events], midi_type=0)


def _raw_smf(*, fmt=1, tracks=1, division=192, body=b"\x00\xff\x2f\x00"):
    return (
        b"MThd" + struct.pack(">IHHH", 6, fmt, tracks, division)
        + b"MTrk" + struct.pack(">I", len(body)) + body
    )


def _semantic_cases():
    """Return one scenario for every letter in the Bosnian alphabet."""
    cases = []

    def add(name, stage, mid, expected, extension=".mid"):
        cases.append({"name": name, "stage": stage, "mid": mid,
                      "expected": expected, "extension": extension})

    add("minimal_parse_roundtrip", "SMF parse/save", _mid([_note(0, 60)]),
        {"container_pass": True, "loadable": True, "note_pairs": 1})
    add("song_multitrack_context", "Song context", _mid([
        [_message("track_name", name="LEAD")] + _identity(0, 0, 0, 0) + _note(0, 72),
        [_message("track_name", name="BASS")] + _identity(1, 0, 0, 33) + _note(1, 36),
    ]), {"container_pass": True, "loadable": True, "tracks": 2})
    add("style_strict_contract", "Style import contract", _style(),
        {"container_pass": True, "loadable": True, "style_minimum": True, "style_strict": True})
    add("style_minimum_header", "Style minimum/header fallback", _style(strict=False),
        {"container_pass": True, "loadable": True, "style_minimum": True, "style_strict": False})
    add("style_uppercase_marker_reject", "Style marker rejection", _style(marker="V1CV1"),
        {"container_pass": True, "loadable": True, "style_minimum": False, "style_strict": False})
    add("style_outside_channel_reject", "Style channel rejection", _style(channel=0),
        {"container_pass": True, "loadable": True, "style_minimum": False, "style_strict": False})
    add("style_unsupported_cc_reject", "Style controller rejection", _style(unsupported_cc=7),
        {"container_pass": True, "loadable": True, "style_minimum": True, "style_strict": False})
    add("sound_bank_program_identity", "Sound identity resolution", _mid([
        _identity(0, 121, 13, 33) + _note(0, 40),
    ]), {"container_pass": True, "loadable": True, "bank_program_events": 3})
    add("sound_multi_program_sequence", "Sound sequence authorization", _mid([_identity(0, 0, 0, 0)
        + _note(0, 60) + _identity(0, 0, 0, 40) + _note(0, 65)]),
        {"container_pass": True, "loadable": True, "program_changes": 2})
    add("drum_kit_key_profile", "Drum Kit+Key profile", _mid([_identity(9, 120, 0, 0)
        + _note(9, 36, 110) + _note(9, 38, 100, delay=48)]),
        {"container_pass": True, "loadable": True, "family": "DRUM_KIT"})
    add("bass_drum_lock", "Bass/Drum timing guard", _mid([
        _identity(9, 120, 0, 0) + _note(9, 36, 110),
        _identity(8, 121, 13, 33) + _note(8, 36, 88),
    ]), {"container_pass": True, "loadable": True, "anchor_pair": True})
    add("guitar_strum_direction", "Guitar strum guard", _mid([_identity(10, 121, 1, 24)
        + _note(10, 52, 88, 144) + _note(10, 57, 82, 144, 3) + _note(10, 64, 76, 144, 3)]),
        {"container_pass": True, "loadable": True, "strum_direction": "UP_PITCH"})
    add("piano_chord_pedal", "Piano chord/pedal guard", _mid([_identity(0, 0, 0, 0)
        + [_message("control_change", channel=0, control=64, value=127)]
        + _note(0, 60, 72, 192) + _note(0, 64, 78, 192) + _note(0, 67, 84, 192)
        + [_message("control_change", channel=0, control=64, value=0)]]),
        {"container_pass": True, "loadable": True, "cc64_contour": [127, 0]})
    add("organ_legato", "Organ velocity/legato guard", _mid([_identity(0, 0, 0, 16)
        + _note(0, 60, 90, 120) + _note(0, 62, 90, 120)]),
        {"container_pass": True, "loadable": True, "legato_candidate": True})
    add("strings_sustain_chord", "Strings sustain/voice-leading guard", _mid([_identity(0, 0, 0, 48)
        + _note(0, 48, 68, 768) + _note(0, 55, 70, 768) + _note(0, 60, 72, 768)]),
        {"container_pass": True, "loadable": True, "sustain_ticks": 768})
    add("brass_expression_contour", "Brass controller guard", _mid([_identity(0, 0, 0, 56)
        + [_message("control_change", channel=0, control=1, value=20),
           _message("pitchwheel", channel=0, pitch=512)] + _note(0, 67, 105)]),
        {"container_pass": True, "loadable": True, "expressive_controllers": True})
    add("reed_breath_contour", "Reed breath/controller guard", _mid([_identity(0, 0, 0, 71)
        + [_message("control_change", channel=0, control=2, value=70),
           _message("aftertouch", channel=0, value=55)] + _note(0, 74, 82)]),
        {"container_pass": True, "loadable": True, "channel_state": True})
    add("synth_lead_pitchbend", "Synth Lead preserve", _mid([_identity(0, 0, 0, 80)
        + [_message("pitchwheel", channel=0, pitch=-1024)] + _note(0, 72, 96)]),
        {"container_pass": True, "loadable": True, "pitchwheel": -1024})
    add("rare_mallet_exact_only", "Rare-family exact-only gate", _mid([_identity(0, 0, 0, 12)
        + _note(0, 72, 100, 48)]), {"container_pass": True, "loadable": True, "exact_only": True})
    add("sfx_permanent_preserve", "SFX/Cycle/Random preserve", _mid([_identity(0, 0, 0, 120)
        + _note(0, 36, 127, 24) + [_message("sysex", data=(1, 2, 3), time=0)]]),
        {"container_pass": True, "loadable": True, "must_preserve": True})
    add("rx_special_pitch", "RX special-pitch protection", _mid([_identity(10, 121, 5, 24)
        + _note(10, 24, 90, 36) + _note(10, 64, 82, 96)]),
        {"container_pass": True, "loadable": True, "special_pitch": 24})
    add("dnc_channel_scoped_pulse", "DNC state/pulse authorization", _mid([_identity(0, 121, 6, 56)
        + [_message("control_change", channel=0, control=80, value=127)]
        + _note(0, 67, 100, 96)
        + [_message("control_change", channel=0, control=80, value=0)]]),
        {"container_pass": True, "loadable": True, "dnc_pulse": [127, 0]})
    add("dnc_cross_channel_negative", "DNC cross-channel negative", _mid([_identity(0, 121, 6, 56)
        + [_message("control_change", channel=1, control=80, value=127)] + _note(0, 67, 100)]),
        {"container_pass": True, "loadable": True, "dnc_authorized": False})
    add("fx_existing_sends", "FX existing-send mutation", _mid([_identity(0, 0, 0, 0)
        + [_message("control_change", channel=0, control=91, value=40),
           _message("control_change", channel=0, control=93, value=20)] + _note(0, 60)]),
        {"container_pass": True, "loadable": True, "fx_controls": [91, 93]})
    add("note_occurrence_overlap", "Stable note occurrence identity", _mid([
        [_message("note_on", channel=0, note=60, velocity=70),
         _message("note_on", channel=0, note=60, velocity=90, time=12),
         _message("note_off", channel=0, note=60, velocity=0, time=48),
         _message("note_off", channel=0, note=60, velocity=0, time=24)]
    ]), {"container_pass": True, "loadable": True, "same_pitch_occurrences": 2})
    add("unmatched_note_negative", "Note pairing negative", _mid([[
        _message("note_on", channel=0, note=60, velocity=80),
    ]]), {"container_pass": True, "loadable": True, "note_pairing_valid": False})
    add("kar_lyrics_preserve", "KAR lyrics preservation", _mid([[
        _message("track_name", name="KARAOKE"), _message("lyrics", text="Test slog"),
    ] + _note(0, 60)]), {"container_pass": True, "loadable": True, "lyrics": 1}, ".kar")

    # The last three stages are deliberately unreadable byte-level negatives.
    cases.append({"name": "container_missing_magic", "stage": "SMF missing-header rejection",
                  "raw": b"NOTMIDI" + _raw_smf()[7:],
                  "expected": {"container_pass": False, "loadable": False}})
    cases.append({"name": "container_truncated_track", "stage": "SMF truncation quarantine",
                  "raw": _raw_smf()[:-2],
                  "expected": {"container_pass": False, "loadable": False}})
    cases.append({"name": "container_illegal_division", "stage": "SMF division rejection",
                  "raw": _raw_smf(division=0),
                  "expected": {"container_pass": False, "loadable": False}})
    assert len(cases) == 30
    return cases


def _paired_cases():
    """Map every certification stage to one positive and one negative fixture."""
    source = {case["name"]: case for case in _semantic_cases()}
    stages = (
        ("SMF container preflight", "minimal_parse_roundtrip", "container_missing_magic"),
        ("Mido load/save roundtrip", "minimal_parse_roundtrip", "container_truncated_track"),
        ("Content type and multitrack context", "song_multitrack_context", "unmatched_note_negative"),
        ("Pa800 strict Style contract", "style_strict_contract", "style_uppercase_marker_reject"),
        ("Style header fallback", "style_minimum_header", "style_outside_channel_reject"),
        ("Style controller allowlist", "style_strict_contract", "style_unsupported_cc_reject"),
        ("Sound Bank/Program identity", "sound_bank_program_identity", "dnc_cross_channel_negative"),
        ("Multi-program authorization", "sound_multi_program_sequence", "unmatched_note_negative"),
        ("Drum Kit+Key resolution", "drum_kit_key_profile", "style_outside_channel_reject"),
        ("Bass/Drum timing lock", "bass_drum_lock", "unmatched_note_negative"),
        ("Guitar strum fingerprint", "guitar_strum_direction", "dnc_cross_channel_negative"),
        ("Piano chord and CC64 contour", "piano_chord_pedal", "unmatched_note_negative"),
        ("Organ velocity/legato guard", "organ_legato", "dnc_cross_channel_negative"),
        ("Strings sustain/voice-leading", "strings_sustain_chord", "unmatched_note_negative"),
        ("Brass expression preservation", "brass_expression_contour", "dnc_cross_channel_negative"),
        ("Reed breath/channel state", "reed_breath_contour", "dnc_cross_channel_negative"),
        ("Synth Lead bend preservation", "synth_lead_pitchbend", "unmatched_note_negative"),
        ("Rare-family exact-only evidence", "rare_mallet_exact_only", "style_unsupported_cc_reject"),
        ("SFX immutable/preserve corridor", "sfx_permanent_preserve", "unmatched_note_negative"),
        ("RX special-pitch protection", "rx_special_pitch", "dnc_cross_channel_negative"),
        ("DNC channel-scoped pulse", "dnc_channel_scoped_pulse", "dnc_cross_channel_negative"),
        ("Existing CC91/93 FX sends", "fx_existing_sends", "style_unsupported_cc_reject"),
        ("Stable note occurrence identity", "note_occurrence_overlap", "unmatched_note_negative"),
        ("KAR lyric preservation", "kar_lyrics_preserve", "container_illegal_division"),
        ("Event verifier negative barrier", "minimal_parse_roundtrip", "unmatched_note_negative"),
        ("Final atomic certification gate", "style_strict_contract", "container_truncated_track"),
    )
    paired = []
    for letter, (stage_name, positive_name, negative_name) in zip(ALPHABET, stages):
        for polarity, source_name in (("positive", positive_name), ("negative", negative_name)):
            original = source[source_name]
            row = dict(original)
            row.update(stage=letter, stage_name=stage_name, polarity=polarity,
                       source_name=source_name,
                       expected=dict(original["expected"],
                                     certification_outcome="PASS" if polarity == "positive" else "REJECT"))
            paired.append(row)
    assert len(paired) == 52
    return paired


def generate(output):
    """Write all fixtures plus a stable evidence manifest and return its rows."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for case in _paired_cases():
        letter = case["stage"]
        extension = case.get("extension", ".mid")
        path = output / f"{letter.lower()}_{case['polarity']}_{case['source_name']}{extension}"
        if "raw" in case:
            path.write_bytes(case["raw"])
        else:
            case["mid"].save(path)
        raw = path.read_bytes()
        preflight = preflight_smf(path)
        actual = {"container_pass": preflight["pass"], "loadable": False}
        if preflight["pass"]:
            loaded = mido.MidiFile(str(path))
            actual["loadable"] = True
            if case["source_name"].startswith("style_"):
                style = analyze_style_import_contract(loaded)
                actual.update(style_minimum=style["minimum_importable"],
                              style_strict=style["strict_export_contract"])
        rows.append({
            "stage": letter,
            "stage_name": case["stage_name"],
            "polarity": case["polarity"],
            "name": case["source_name"],
            "file": path.name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
            "expected": case["expected"],
            "observed": actual,
        })
    manifest = {"schema": SCHEMA, "scope":"STRUCTURAL_AND_MANIFEST_COVERAGE_NOT_HARDWARE_CERTIFICATION","serialization":"STANDARD_MIDI_FILE","scenario_count": len(rows), "scenarios": rows}
    (output / "PROCESS_CERTIFICATION_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", default="process_certification_midis")
    args = parser.parse_args(argv)
    rows = generate(args.output)
    print(f"Generated {len(rows)} process-certification MIDI/KAR fixtures in {args.output}")


if __name__ == "__main__":
    main()