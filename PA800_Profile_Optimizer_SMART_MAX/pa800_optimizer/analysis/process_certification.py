"""A–Z certification matrix for the complete optimizer lifecycle."""
from __future__ import annotations


def _stage(code,name,process,positive,negative):
    return {'stage':code,'name':name,'process':process,'positive_tests':positive,'negative_tests':negative,'required_fixture_polarities':['positive','negative']}


PROCESS_STAGES=(
    _stage('A','Artifact integrity','Factory/profile/package hashes',['tests/test_release_integrity.py::test_release_audit_passes'],['tests/test_optional_deps.py::OptionalDependencyTests::test_missing_required_dependency_disables_core']),
    _stage('B','Binary SMF preflight','Header, chunks and track-length validation',['tests/test_smf_preflight.py::test_preflight_accepts_complete_container'],['tests/test_smf_preflight.py::test_preflight_quarantines_truncated_track']),
    _stage('C','Container recovery','Tolerant load and deterministic quarantine',['tests/test_compatibility.py::test_recovery_package_is_deterministic_and_keeps_original'],['tests/test_corrupt_midi_corpus.py::test_eighty_golden_mid_kar_containers_are_deterministically_rejected']),
    _stage('D','Doctor repair','Pairing, tempo, duration and channel-mode repair',['tests/test_midi_doctor.py::test_doctor_repairs_structural_note_and_track_errors'],['tests/test_midi_doctor.py::test_conflicting_same_tick_tempo_is_unrecoverable_not_guessed']),
    _stage('E','Environment compatibility','Tempo/program/exporter compatibility',['tests/test_compatibility.py::test_redundant_same_tempo_is_safe_but_conflict_is_not'],['tests/test_compatibility.py::test_optimizer_emits_recovery_package_for_unrecoverable_container']),
    _stage('F','Format/content detection','Explicit and automatic Song/Style classification',['tests/test_content_type.py::ContentTypeTests::test_auto_style_from_cv'],['tests/test_automation.py::test_ambiguous_input_falls_back_to_preserve_suggest']),
    _stage('G','Ground-truth context','Track-function and section scoring',['tests/test_context_ground_truth.py::test_valid_ground_truth_and_perfect_prediction_pass'],['tests/test_context_ground_truth.py::test_wrong_function_and_boundary_fail_roadmap_gates']),
    _stage('H','High-level automation','Autopilot mode and safe policy selection',['tests/test_automation.py::test_high_confidence_style_uses_strong_apply'],['tests/test_automation.py::test_missing_factory_coverage_falls_back_to_preserve']),
    _stage('I','Identity/profile resolution','Exact Sound/address/name/support resolution',['tests/test_registry.py::T::test_load'],['tests/test_registry.py::T::test_conflicts_guarded']),
    _stage('J','Kit/key evidence','Exact Drum Kit+Key profile routing',['tests/test_drum_key_profile.py::T::test_standard_rx3_key36'],['tests/test_factory_usage_meter.py::test_usage_meter_fails_if_a_blocked_note_was_mutated']),
    _stage('K','Korg Style contract','Format-0 marker-separated Pa800 import contract',['tests/test_style_import_contract.py::test_official_marker_style_contract_accepts_strict_format_zero_file'],['tests/test_style_import_contract.py::test_style_contract_rejects_uppercase_marker_outside_channel_and_cc']),
    _stage('L','Low-level RX/DNC guard','Sensitive notes/controllers and channel-scoped state',['tests/test_rx_guard.py::T::test_low_rx_velocity_survives'],['tests/test_articulation_director.py::test_expressive_growl_requires_hardware_e3_for_apply']),
    _stage('M','Mapping Sound/FX','Voice ranking, address rewrite and bounded FX',['tests/test_optimizer.py::T::test_auto_sound_and_fx_change_end_to_end'],['tests/test_authority_quality.py::test_final_quality_gate_rejects_applied_broad_voice_without_e3']),
    _stage('N','Note intent','Metric, passing, anchor and special-note intent',['tests/test_intent.py::T::test_bass_intents'],['tests/test_preserve_unknown.py::T::test_unknown_exact_sound_preserved']),
    _stage('O','Orchestration context','Sections, functions, balance and interaction analysis',['tests/test_musical_context.py::test_song_context_analysis_is_analyzer_only_and_finds_sections'],['tests/test_context_ground_truth.py::test_invalid_labels_are_rejected_without_guessing']),
    _stage('P','Performance direction','Phrase/section/function bounded performance shaping',['tests/test_performance_director.py::test_e2_style_phrase_can_apply_bounded_offset_and_protect_notes'],['tests/test_performance_director.py::test_song_e1_context_stays_shadow_even_when_apply_requested']),
    _stage('Q','Quantile velocity','Profile curve, conductor and IQR preservation',['tests/test_velocity_conductor.py::test_different_instruments_receive_different_normal_centers'],['tests/test_velocity_conductor.py::test_protected_note_velocity_is_untouched']),
    _stage('R','Rhythm/timing','Profile residual and instrument timing fingerprints',['tests/test_instrument_engine_guards.py::test_bass_timing_follows_nearest_drum_shift'],['tests/test_instrument_fingerprints.py::test_fingerprint_audit_detects_shortened_string_tail_and_controller_change']),
    _stage('S','Sustain/gate','Gate evidence, damper, legato and tail preservation',['tests/test_instrument_engine_guards.py::test_piano_gate_is_not_rewritten_while_damper_is_held'],['tests/test_gate_null_profile.py::test_null_gate_profile_is_preserved_without_crash']),
    _stage('T','Technique/articulation','DNC audition, insertion and pulse ordering',['tests/test_articulation_director.py::test_exact_dnc_slide_apply_inserts_verified_cc80_pulse'],['tests/test_verifier.py::T::test_articulation_pulse_must_bracket_note_on_at_same_tick']),
    _stage('U','Usage accounting','Per-note available/resolved/used/mutated/blocked meter',['tests/test_factory_usage_meter.py::test_usage_meter_classifies_every_note_once_and_counts_mutations'],['tests/test_factory_usage_batch.py::test_batch_aggregation_rejects_missing_usage_meter']),
    _stage('V','Verifier','Canonical note/controller/address authorization diff',['tests/test_verifier.py::T::test_equal'],['tests/test_verifier.py::T::test_missing_note_off_fails']),
    _stage('W','Workstation/commit','Locking, rollback, journal and atomic artifact commit',['tests/test_runtime_safety.py::test_artifact_group_commits_together'],['tests/test_runtime_safety.py::test_artifact_group_rolls_back_on_second_replace']),
    _stage('X','eXport/report/release','Reports, package data, GUI state and wheel inputs',['tests/test_release_integrity.py::test_runtime_profile_package_data_present'],['tests/test_gui_state.py::test_suffix_is_path_safe']),
    _stage('Y','Yield/determinism/stress','Same-input determinism and bounded stress behavior',['tests/test_optimizer.py::T::test_deterministic'],['tests/test_corrupt_midi_corpus.py::test_eighty_golden_mid_kar_containers_are_deterministically_rejected']),
    _stage('Z','Zero unauthorized changes','Authority ledger and final quality gate',['tests/test_authority_quality.py::test_final_quality_gate_passes_consistent_safe_report'],['tests/test_authority_quality.py::test_final_quality_gate_rejects_instrument_fingerprint_regression']),
)


def evaluate_process_coverage(available_nodeids,fixture_manifest):
    available=set(available_nodeids);scenarios=(fixture_manifest or {}).get('scenarios') or [];by_stage={}
    for row in scenarios:by_stage.setdefault(str(row.get('stage','')).upper(),set()).add(str(row.get('polarity','')).lower())
    rows=[]
    for stage in PROCESS_STAGES:
        missing_positive=[node for node in stage['positive_tests'] if node not in available];missing_negative=[node for node in stage['negative_tests'] if node not in available];polarities=by_stage.get(stage['stage'],set());missing_fixtures=[value for value in stage['required_fixture_polarities'] if value not in polarities]
        row={**stage,'missing_positive_tests':missing_positive,'missing_negative_tests':missing_negative,'fixture_polarities':sorted(polarities),'missing_fixture_polarities':missing_fixtures};row['pass']=not missing_positive and not missing_negative and not missing_fixtures;rows.append(row)
    return {'schema':'PA800_PROCESS_CERTIFICATION_AZ_V1','stages':rows,'stage_count':len(rows),'passed_stages':sum(row['pass'] for row in rows),'pass':all(row['pass'] for row in rows)}