"""Cross-process negative/recovery matrix for the A-to-Z validation pack.

These tests intentionally exercise refusal and recovery paths.  A process is
not considered covered merely because its happy path succeeds.
"""
from __future__ import annotations

import copy
import json
import os
import socket
from types import SimpleNamespace
from unittest.mock import patch

import mido
import pytest

from pa800_optimizer.analysis.hardware_campaign import (
    MAJOR_FX_ROLES,
    MAJOR_VOICE_FAMILIES,
    campaign_template,
    evaluate_hardware_campaign,
)
from pa800_optimizer.analysis.style_import_contract import analyze_style_import_contract
from pa800_optimizer.authority import authorize
from pa800_optimizer.instruments.guards import (
    expressive_controller_channels,
    sustained_tail_note_ids,
)
from pa800_optimizer.instruments.policies import policy_for, profile_evidence_allows_mutation
from pa800_optimizer.models import Change, NoteEvent
from pa800_optimizer.runtime_safety import OutputLock, commit_artifacts, temp_path_for
from pa800_optimizer.verifier import verify


def _base_midi(*, midi_type=1, channel=0):
    mid = mido.MidiFile(type=midi_type, ticks_per_beat=192)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.extend(
        [
            mido.Message("control_change", channel=channel, control=0, value=121, time=0),
            mido.Message("control_change", channel=channel, control=32, value=3, time=0),
            mido.Message("program_change", channel=channel, program=0, time=0),
            mido.Message("control_change", channel=channel, control=91, value=20, time=0),
            mido.Message("note_on", channel=channel, note=60, velocity=90, time=0),
            mido.Message("note_off", channel=channel, note=60, velocity=0, time=96),
        ]
    )
    return mid


def _valid_style():
    mid = mido.MidiFile(type=0, ticks_per_beat=192)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.extend(
        [
            mido.MetaMessage("marker", text="v1cv1", time=0),
            mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0),
            mido.Message("control_change", channel=8, control=0, value=121, time=0),
            mido.Message("control_change", channel=8, control=32, value=13, time=0),
            mido.Message("program_change", channel=8, program=33, time=0),
            mido.Message("control_change", channel=8, control=11, value=100, time=0),
            mido.Message("note_on", channel=8, note=40, velocity=80, time=0),
            mido.Message("note_off", channel=8, note=40, velocity=0, time=96),
        ]
    )
    return mid


def _passing_campaign():
    data = campaign_template()
    data["device"].update(
        {
            "os_version": "2.03",
            "musical_resources_version": "2.03",
            "set_id": "FACTORY",
            "audio_chain_id": "LINE_OUT_24BIT",
        }
    )
    for family in MAJOR_VOICE_FAMILIES:
        data["records"].extend(
            {
                "kind": "voice",
                "family": family,
                "top1_correct": True,
                "top3_correct": True,
                "false_positive": False,
                "preference": "same",
            }
            for _ in range(30)
        )
    for role in MAJOR_FX_ROLES:
        data["records"].extend(
            {"kind": "fx", "role": role, "preference": "same", "mud_failure": False}
            for _ in range(30)
        )
    data["records"].extend(
        {"kind": "dnc", "address": f"121.18.{index}", "status": "PASS"}
        for index in range(23)
    )
    return data


# Authority / verifier -----------------------------------------------------


@pytest.mark.parametrize(
    "mutation,evidence,kwargs,reason",
    [
        ("SOUND_SAFE_GM", "E3", {"conflict": True}, "identity_or_multi_program_conflict"),
        ("FX_DRY_GUARD", "E3", {"preserve_preset": True}, "preserve_preset_blocks_creative_mutation"),
        ("ARTICULATION_EXPRESSIVE", "E2", {"sensitive": True}, "requires_E3_or_higher"),
        ("INSERT_MASTER_FX", "E3", {}, "serialization_or_hardware_schema_not_authorized"),
    ],
)
def test_authority_negative_matrix_refuses_unsafe_apply(mutation, evidence, kwargs, reason):
    decision = authorize(mutation, evidence, applied=True, **kwargs)
    assert not decision.allowed
    assert decision.reason == reason


def test_verifier_rejects_unlisted_controller_change_even_when_note_change_is_valid():
    before = _base_midi()
    after = copy.deepcopy(before)
    after.tracks[0].insert(4, mido.Message("control_change", channel=0, control=7, value=99, time=0))
    result = verify(before, after, authorized_note_changes=[])
    assert not result["pass"]
    assert not result["immutable_events"]


def test_verifier_rejects_stale_note_authority_and_address_reordering():
    before = _base_midi()
    after = copy.deepcopy(before)
    after.tracks[0][4] = after.tracks[0][4].copy(velocity=96)
    stale = Change(0, 4, "velocity", 89, 96, "stale", "", channel=0, note=60, occurrence=0)
    assert not verify(before, after, authorized_note_changes=[stale])["canonical_note_diff"]

    reordered = copy.deepcopy(before)
    reordered.tracks[0][0], reordered.tracks[0][1] = reordered.tracks[0][1], reordered.tracks[0][0]
    result = verify(before, reordered, authorized_sound_targets={(0, 0): (121, 3, 0)})
    assert not result["pass"]
    assert not result["address_event_order"]


def test_verifier_rejects_partial_or_wrong_tick_articulation_pulse():
    before = _base_midi()
    after = copy.deepcopy(before)
    after.tracks[0].insert(4, mido.Message("control_change", channel=0, control=80, value=127, time=0))
    authorization = [(0, 0, 0, 80, 127, 60, 0), (0, 0, 0, 80, 0, 60, 0)]
    result = verify(before, after, authorized_articulation_insertions=authorization)
    assert not result["pass"]
    assert not result["articulation_events"]


# Style contract / hardware evidence --------------------------------------


def test_style_contract_rejects_second_marker_without_time_signature():
    mid = _valid_style()
    mid.tracks[0].extend(
        [
            mido.MetaMessage("marker", text="v2cv1", time=96),
            mido.Message("note_on", channel=8, note=41, velocity=80, time=0),
            mido.Message("note_off", channel=8, note=41, velocity=0, time=96),
        ]
    )
    result = analyze_style_import_contract(mid)
    assert not result["minimum_importable"]
    assert not result["checks"]["time_signature_at_each_marker"]
    assert result["markers"][1]["minimum_header"] is False


def test_style_contract_unsupported_cc_blocks_strict_export_but_not_minimum_import():
    mid = _valid_style()
    mid.tracks[0].append(mido.Message("control_change", channel=8, control=7, value=100, time=0))
    result = analyze_style_import_contract(mid)
    assert result["minimum_importable"]
    assert not result["strict_export_contract"]
    assert result["unsupported_event_count"] == 1


def test_hardware_campaign_unknown_dnc_and_duplicate_addresses_never_become_e3():
    data = _passing_campaign()
    dnc = [row for row in data["records"] if row["kind"] == "dnc"]
    dnc[0]["status"] = "UNKNOWN"
    for row in dnc[1:]:
        row["address"] = "121.18.1"
    result = evaluate_hardware_campaign(data)
    assert not result["pass"]
    assert not result["gates"]["dnc_23_addresses_covered"]
    assert not result["gates"]["dnc_all_23_pass"]


def test_hardware_campaign_exact_false_positive_threshold_is_exclusive():
    data = _passing_campaign()
    piano = [row for row in data["records"] if row.get("kind") == "voice" and row.get("family") == "PIANO"]
    piano[0]["false_positive"] = True
    result = evaluate_hardware_campaign(data)
    row = next(item for item in result["voice_families"] if item["family"] == "PIANO")
    assert row["false_positive_rate"] > 0.02
    assert not row["auto_eligible"]
    assert not result["gates"]["voice_auto_gates_pass"]


# Atomic commit / recovery -------------------------------------------------


def test_foreign_host_lock_is_not_deleted_as_stale(tmp_path):
    target = tmp_path / "result.mid"
    lock = target.with_name(target.name + ".lock")
    lock.write_text(json.dumps({"pid": 99999999, "host": "different-host"}), encoding="utf-8")
    with pytest.raises(RuntimeError):
        OutputLock(target).acquire()
    assert lock.exists()


def test_malformed_local_lock_is_recovered_and_released(tmp_path):
    target = tmp_path / "result.mid"
    lock = target.with_name(target.name + ".lock")
    lock.write_text("not-json", encoding="utf-8")
    with OutputLock(target):
        payload = json.loads(lock.read_text(encoding="utf-8"))
        assert payload["host"] == socket.gethostname() and payload["pid"] == os.getpid()
    assert not lock.exists()


def test_atomic_group_restores_first_target_when_second_backup_fails(tmp_path):
    first = tmp_path / "out.mid"
    second = tmp_path / "out.json"
    first.write_text("old-midi", encoding="utf-8")
    second.write_text("old-report", encoding="utf-8")
    tmp_first = temp_path_for(first)
    tmp_second = temp_path_for(second)
    tmp_first.write_text("new-midi", encoding="utf-8")
    tmp_second.write_text("new-report", encoding="utf-8")

    import pa800_optimizer.runtime_safety as runtime_safety

    real_replace = runtime_safety.os.replace
    calls = {"count": 0}

    def fail_second_backup(source, destination):
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("simulated backup failure")
        return real_replace(source, destination)

    with patch.object(runtime_safety.os, "replace", side_effect=fail_second_backup):
        with pytest.raises(OSError):
            commit_artifacts([(tmp_first, first), (tmp_second, second)])
    assert first.read_text(encoding="utf-8") == "old-midi"
    assert second.read_text(encoding="utf-8") == "old-report"
    assert not tmp_first.exists() and not tmp_second.exists()


# Rare / family guards -----------------------------------------------------


@pytest.mark.parametrize("family", ["SYNTH_LEAD", "MALLET", "PLUCK", "ETHNIC"])
def test_rare_exact_only_policy_rejects_unstable_or_family_aggregate_profile(family):
    policy = policy_for(family)
    unstable = {"support": {"grade": "STRONG"}, "_profile_stability": "CONTEXT_DEPENDENT"}
    aggregate = {
        "support": {"grade": "STRONG"},
        "_profile_stability": "STABLE",
        "_velocity_basis": "FACTORY_FAMILY_AGGREGATE",
    }
    assert policy["exact_only"]
    assert not profile_evidence_allows_mutation(policy, unstable)
    assert not profile_evidence_allows_mutation(policy, aggregate)


def test_sustained_and_expressive_guards_are_channel_scoped():
    long_note = NoteEvent(0, 0, 60, 80, 0, 192, 1, 2, occurrence=0)
    short_note = NoteEvent(0, 1, 62, 80, 0, 48, 3, 4, occurrence=0)
    contexts = {
        (0, 0): SimpleNamespace(family="STRINGS"),
        (0, 1): SimpleNamespace(family="PIANO"),
    }
    assert sustained_tail_note_ids([long_note, short_note], contexts, 192) == {(0, 0, 60, 0)}

    mid = mido.MidiFile(type=1, ticks_per_beat=192)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.extend(
        [
            mido.Message("control_change", channel=0, control=1, value=80, time=0),
            mido.Message("control_change", channel=1, control=1, value=80, time=0),
        ]
    )
    expressive_contexts = {
        (0, 0): SimpleNamespace(family="BRASS"),
        (0, 1): SimpleNamespace(family="PIANO"),
    }
    assert expressive_controller_channels(mid, expressive_contexts) == {(0, 0)}