from types import SimpleNamespace

from pa800_optimizer.authority import audit_neural_factory_boundary,authorize
from pa800_optimizer.config import OptimizeConfig
from pa800_optimizer.models import Change
from pa800_optimizer.quality_gate import evaluate_quality_gate


def test_central_authority_matrix_enforces_evidence_and_safety():
    assert authorize('SOUND_SAFE_GM','E2',applied=True).allowed
    assert not authorize('SOUND_BROAD','E2',applied=True).allowed
    assert authorize('SOUND_BROAD','E3',applied=True).allowed
    assert not authorize('FX_SECTION_DEPTH','E2',applied=True).allowed
    assert authorize('FX_SECTION_DEPTH','E3',applied=True).allowed
    assert not authorize('VELOCITY_PROFILE','E2',applied=True,sensitive=True).allowed
    assert not authorize('PERFORMANCE_SECTION','E2',applied=True,preserve_preset=True).allowed
    assert not authorize('INSERT_MASTER_FX','E3',applied=True).allowed
    assert authorize('NEURAL_TIMING_EXPLICIT','E2',applied=True).allowed


def report_fixture():
    return SimpleNamespace(
        contexts=[{'track':0,'channel':1,'evidence_level':'E2','conflict':False}],
        midi_repair={'pass':True,'repairs':[],'repair_count':0,'canonical_replay':{'pass':True}},compatibility={'safe_for_optimization':True},verifier={'pass':True,'authorized_articulation_events':0,'authorized_sound_channels':0,'authorized_fx_channels':0},
        velocity_conductor={'contexts':[{'iqr_retention':.8}]},mix_fx_director={'enabled':True,'contexts':[],'authorized_channels':0},performance_director={'pass':True},articulations={'inserted_events':0,'contexts':[]},intelligence=[],changes=[],mutation_ledger=[],factory_usage_meter={'pass':True},instrument_director={'pass':True},musical_understanding={'schema':'PA800_MUSICAL_UNDERSTANDING_V2','analyzer_only':True,'mutations':0,'authority_granted':False},agent_mesh={})


def test_final_quality_gate_passes_consistent_safe_report():
    authority,gate=evaluate_quality_gate(report_fixture(),OptimizeConfig.for_mode('live'))
    assert authority['pass'] and gate['pass'] and gate['score_percent']==100.0
    assert gate['classification']=='TECHNICAL_PASS_PA800_UNVERIFIED'
    assert gate['certification']['technical_pass'] is True and gate['certification']['pa800_hardware_verified'] is False
    assert gate['check_status']['fx_contours_preserved']=='N/A'


def test_quality_gate_does_not_report_empty_optional_checks_as_passed():
    report=report_fixture();report.velocity_conductor={'contexts':[]};report.performance_director={}
    _authority,gate=evaluate_quality_gate(report,OptimizeConfig.for_mode('live'))
    assert gate['check_status']['velocity_iqr_retained']=='N/A'
    assert gate['check_status']['performance_authorized']=='N/A'


def test_final_quality_gate_rejects_applied_broad_voice_without_e3():
    report=report_fixture();report.intelligence=[{'track':0,'channel':1,'action':'AUTO_CANDIDATE','evidence_level':'E2','sound_apply_status':'applied','current_sound':'Piano'}];report.verifier['authorized_sound_channels']=1
    authority,gate=evaluate_quality_gate(report,OptimizeConfig.for_mode('live'))
    assert not authority['pass'] and not gate['pass'] and 'authority_ledger' in gate['failed_checks']


def test_final_quality_gate_rejects_fx_contour_or_authorization_mismatch():
    report=report_fixture();report.mix_fx_director={'enabled':True,'authorized_channels':1,'contexts':[{'track':0,'channel':1,'changes':2,'apply_status':'applied_bounded_dry_guard','evidence_level':'E1','control_audit':[{'contour_preserved':False}]}]}
    _authority,gate=evaluate_quality_gate(report,OptimizeConfig.for_mode('live'))
    assert not gate['pass'] and {'fx_contours_preserved','fx_authorization_count_consistent'}<=set(gate['failed_checks'])


def test_final_quality_gate_rejects_incomplete_factory_usage_accounting():
    report=report_fixture();report.factory_usage_meter={'pass':False}
    _authority,gate=evaluate_quality_gate(report,OptimizeConfig.for_mode('live'))
    assert not gate['pass'] and 'factory_usage_complete' in gate['failed_checks']


def test_final_quality_gate_rejects_instrument_fingerprint_regression():
    report=report_fixture();report.instrument_director={'pass':False}
    _authority,gate=evaluate_quality_gate(report,OptimizeConfig.for_mode('live'))
    assert not gate['pass'] and 'instrument_fingerprints_preserved' in gate['failed_checks']


def test_direct_fx_path_is_recorded_in_authority_ledger():
    report=report_fixture();report.mix_fx_director={'enabled':False,'contexts':[]}
    report.intelligence=[{'track':0,'channel':1,'action':'PRESERVE','evidence_level':'E1','sound_apply_status':'disabled','current_sound':'Piano','fx_send_changes':2}]
    report.verifier['authorized_fx_channels']=1
    authority,gate=evaluate_quality_gate(report,OptimizeConfig.for_mode('live'))
    direct=[row for row in authority['decisions'] if row['source']=='sound_fx_intelligence']
    assert direct and direct[0]['mutation']=='FX_DRY_GUARD' and direct[0]['allowed']
    assert gate['pass']


def test_style_export_gate_requires_minimum_import_contract():
    report=report_fixture();report.style_import_contract={'minimum_importable':False}
    cfg=OptimizeConfig.for_mode('live');cfg.require_style_import_contract=True
    _authority,gate=evaluate_quality_gate(report,cfg)
    assert not gate['pass'] and 'style_import_contract_ready' in gate['failed_checks']


def test_preserve_gate_rejects_any_mutation():
    report=report_fixture();report.mutation_ledger=[{'mutation':'NOTE_VELOCITY'}]
    _authority,gate=evaluate_quality_gate(report,OptimizeConfig.for_mode('preserve'))
    assert not gate['pass'] and 'strict_preserve_has_no_mutations' in gate['failed_checks']


def test_quality_gate_rejects_understanding_layer_that_claims_mutation_authority():
    report=report_fixture();report.musical_understanding['authority_granted']=True
    _authority,gate=evaluate_quality_gate(report,OptimizeConfig.for_mode('live'))
    assert not gate['pass'] and 'musical_understanding_is_analysis_only' in gate['failed_checks']


def test_quality_gate_rejects_hidden_creative_workflow_mutation():
    report=report_fixture();report.musician_workflow={'schema':'PA800_MUSICIAN_WORKFLOW_V1','analyzer_only':True,'authority_granted':False,'creative_mutations':1,'cards':{'creative_tools':{'applied_mutations':1}}}
    _authority,gate=evaluate_quality_gate(report,OptimizeConfig.for_mode('live'))
    assert not gate['pass'] and 'musician_workflow_has_no_hidden_creative_authority' in gate['failed_checks']


def _trained_config():
    cfg=OptimizeConfig.for_mode('natural');cfg.apply_trained_rhythm_model=True;cfg.trained_rhythm_model_path='encoder.json';cfg.trained_rhythm_only=True;return cfg


def _trained_report():
    report=report_fixture();report.workstation={'trained_rhythm_application':{'explicit_user_authority':True,'velocity_features_applied':0,'pitch_features_applied':0,'voice_settings_applied':0}};report.mix_fx_director={'enabled':False,'mutations':0,'contexts':[]};report.articulations={'inserted_events':0,'contexts':[]};report.velocity_conductor={'contexts':[]};report.changes=[Change(0,1,'timing',10,12,'explicit_trained_rhythm_model',channel=0,note=60,occurrence=0,protected=False),Change(0,2,'gate',40,42,'explicit_trained_note_duration',channel=0,note=60,occurrence=0,protected=False)];report.verifier.update({'authorized_note_changes':2,'authorized_sound_channels':0,'authorized_fx_channels':0,'authorized_articulation_events':0});return report


def test_explicit_neural_pass_allows_only_timing_and_gate():
    report=_trained_report();boundary=audit_neural_factory_boundary(report,_trained_config());authority,gate=evaluate_quality_gate(report,_trained_config())
    assert boundary['pass'] and authority['pass'] and gate['pass']
    mutations={row['mutation'] for row in authority['decisions']};assert {'NEURAL_TIMING_EXPLICIT','NEURAL_GATE_EXPLICIT'}<=mutations


def test_neural_pass_cannot_hide_factory_velocity_or_voice_rewrite():
    report=_trained_report();report.changes.append(Change(0,3,'velocity',80,90,'bad_neural_velocity',channel=0,note=62,occurrence=0,protected=False));report.intelligence=[{'sound_apply_status':'applied','fx_send_changes':0}];report.verifier['authorized_sound_channels']=1
    boundary=audit_neural_factory_boundary(report,_trained_config());_authority,gate=evaluate_quality_gate(report,_trained_config())
    assert not boundary['pass'] and {'only_timing_and_gate_note_changes','factory_velocity_unchanged','no_sound_or_kit_rewrite'}<=set(boundary['violations'])
    assert not gate['pass'] and 'neural_factory_authority_boundary' in gate['failed_checks']