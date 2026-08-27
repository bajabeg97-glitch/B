"""Final cross-module quality gate executed after event-level verification."""
from __future__ import annotations

from .authority import audit_neural_factory_boundary,build_authority_ledger
from .agents import _valid_agent_mesh
from .neural.pattern_advisor import validate_pattern_advisor


def evaluate_quality_gate(report,config):
    authority=build_authority_ledger(report,config);neural_boundary=audit_neural_factory_boundary(report,config);minimum_iqr=float(getattr(config,'velocity_min_iqr_retention',.75));velocity_rows=(report.velocity_conductor or {}).get('contexts',[]);fx_rows=(report.mix_fx_director or {}).get('contexts',[]);performance=report.performance_director or {};checks={}
    def record(name,value,applicable=True):
        checks[name]=bool(value) if applicable else None
    repair=report.midi_repair or {}
    doctor_applicable=bool(getattr(config,'enable_midi_repair',False)) or bool(repair.get('repairs'))
    record('doctor_integrity',bool(repair.get('pass')) and bool(repair.get('canonical_replay',{}).get('pass')),doctor_applicable)
    record('compatibility_safe',bool((report.compatibility or {}).get('safe_for_optimization')))
    record('event_level_verifier',bool((report.verifier or {}).get('pass')))
    record('mutation_arbiter',bool((getattr(report,'mutation_arbitration',{}) or {}).get('pass')),bool(getattr(report,'mutation_arbitration',{})))
    record('musical_decision_plan',bool((getattr(report,'musical_decision_plan',{}) or {}).get('pass')),bool(getattr(report,'musical_decision_plan',{})))
    premium_budget=((getattr(report,'workstation',{}) or {}).get('mutation_budget_audit_after_rollback') or (getattr(report,'workstation',{}) or {}).get('mutation_budget_audit_after_selective_rollback') or (getattr(report,'workstation',{}) or {}).get('mutation_budget_audit') or {})
    record('premium_mutation_budget',bool(premium_budget.get('pass')),bool(premium_budget))
    tx=((getattr(report,'workstation',{}) or {}).get('transaction_coverage') or {})
    record('transaction_coverage_complete',bool(tx.get('pass')),bool(tx))
    sound_tx=((getattr(report,'workstation',{}) or {}).get('structural_sound_transaction') or {})
    record('structural_sound_replay',bool((sound_tx.get('canonical_replay') or {}).get('pass')),bool(sound_tx.get('accepted')))
    art_tx=((getattr(report,'articulations',{}) or {}).get('structural_transaction') or {})
    record('structural_articulation_replay',bool((art_tx.get('canonical_replay') or {}).get('pass')),bool(art_tx.get('accepted')))
    record('authority_ledger',bool(authority['pass']))
    record('neural_factory_authority_boundary',bool(neural_boundary['pass']),bool(neural_boundary['applicable']))
    record('velocity_iqr_retained',all(float(row.get('iqr_retention',0.0))+1e-9>=minimum_iqr for row in velocity_rows),bool(velocity_rows))
    fx_audits=[item for row in fx_rows for item in row.get('control_audit',[])]
    record('fx_contours_preserved',all(item.get('contour_preserved') is True for item in fx_audits),bool(fx_audits))
    record('performance_authorized',bool(performance.get('pass')),bool(performance))
    expression_events=(performance.get('expression_event_mutations') or [])
    record('solo_expression_cc11_authorized',len(expression_events)==int((report.verifier or {}).get('authorized_expression_events',0)) and int(performance.get('expression_inserts',0))==0,bool(expression_events))
    record('factory_usage_complete',bool((report.factory_usage_meter or {}).get('pass')))
    record('instrument_fingerprints_preserved',bool((report.instrument_director or {}).get('pass')))
    understanding=getattr(report,'musical_understanding',{}) or {}
    understanding_schema=understanding.get('schema')
    record('musical_understanding_is_analysis_only',understanding_schema in ('PA800_MUSICAL_UNDERSTANDING_V1','PA800_MUSICAL_UNDERSTANDING_V2') and understanding.get('analyzer_only') is True and int(understanding.get('mutations',-1))==0 and understanding.get('authority_granted') is False)
    section_narrative=getattr(report,'section_narrative',{}) or {}
    record('section_narrative_v3_has_no_self_authority',section_narrative.get('schema')=='PA800_SECTION_NARRATIVE_V3' and section_narrative.get('analyzer_only') is True and int(section_narrative.get('mutations',-1))==0 and section_narrative.get('authority_granted') is False and int((section_narrative.get('automation') or {}).get('applied_actions',-1))==0,bool(section_narrative))
    family_intent=getattr(report,'family_intent',{}) or {}
    record('family_intent_v1_has_no_self_authority',family_intent.get('schema')=='PA800_FAMILY_INTENT_V1' and family_intent.get('analyzer_only') is True and int(family_intent.get('mutations',-1))==0 and family_intent.get('authority_granted') is False and int((family_intent.get('automation') or {}).get('applied_actions',-1))==0,bool(family_intent))
    intent=getattr(report,'instrument_intent',{}) or {}
    record('instrument_intent_v3_has_no_self_authority',intent.get('schema')=='PA800_INSTRUMENT_INTENT_V3' and intent.get('analyzer_only') is True and int(intent.get('mutations',-1))==0 and intent.get('authority_granted') is False and int((intent.get('automation') or {}).get('applied_actions',-1))==0,bool(intent))
    pattern_advisor=getattr(report,'pattern_advisor',{}) or {}
    record('pattern_advisor_is_analysis_only',validate_pattern_advisor(pattern_advisor).get('pass'),bool(pattern_advisor))
    workflow=getattr(report,'musician_workflow',{}) or {}
    creative=(workflow.get('cards',{}).get('creative_tools',{}) or {})
    record('musician_workflow_has_no_hidden_creative_authority',workflow.get('schema')=='PA800_MUSICIAN_WORKFLOW_V1' and workflow.get('analyzer_only') is True and workflow.get('authority_granted') is False and int(workflow.get('creative_mutations',-1))==0 and int(creative.get('applied_mutations',-1))==0,bool(workflow))
    agent_mesh=getattr(report,'agent_mesh',{}) or {}
    record('agent_mesh_is_analysis_only',_valid_agent_mesh(agent_mesh),bool(agent_mesh))
    song_map=getattr(report,'song_map',{}) or {}
    record('song_map_is_analysis_only',song_map.get('schema')=='PA800_SONG_MAP_V1' and song_map.get('analyzer_only') is True and song_map.get('authority_granted') is False and int(song_map.get('mutations',-1))==0,bool(song_map))
    phrase_doctor=getattr(report,'phrase_doctor',{}) or {}
    record('phrase_doctor_is_shadow_only',phrase_doctor.get('schema')=='PA800_PHRASE_DOCTOR_V1' and phrase_doctor.get('analyzer_only') is True and phrase_doctor.get('authority_granted') is False and int(phrase_doctor.get('mutations',-1))==0 and int(phrase_doctor.get('applied_actions',-1))==0,bool(phrase_doctor))
    repair_previews=getattr(report,'repair_previews',{}) or {}
    record('repair_previews_are_audition_only',repair_previews.get('schema')=='PA800_REPAIR_PREVIEWS_V1' and repair_previews.get('analyzer_only') is True and repair_previews.get('authority_granted') is False and int(repair_previews.get('mutations',-1))==0 and int(repair_previews.get('applied_actions',-1))==0 and not any(row.get('applied') for row in repair_previews.get('previews',[])),bool(repair_previews))
    style_required=bool(getattr(config,'require_style_import_contract',False))
    record('style_import_contract_ready',bool((getattr(report,'style_import_contract',{}) or {}).get('minimum_importable')),style_required)
    record('articulation_event_count_consistent',int((report.articulations or {}).get('inserted_events',0))==int((report.verifier or {}).get('authorized_articulation_events',0)))
    record('sound_authorization_count_consistent',sum(str(row.get('sound_apply_status','')).startswith('applied') for row in report.intelligence or [])==int((report.verifier or {}).get('authorized_sound_channels',0)))
    if (report.mix_fx_director or {}).get('enabled'):
        expected_fx=int((report.mix_fx_director or {}).get('authorized_channels',0))
    else:expected_fx=len({(row.get('track'),row.get('channel')) for row in report.intelligence or [] if int(row.get('fx_send_changes') or 0)>0})
    record('fx_authorization_count_consistent',expected_fx==int((report.verifier or {}).get('authorized_fx_channels',0)))
    strict_preserve=str(getattr(config,'mode',''))=='preserve' or str(getattr(config,'export_preset',''))=='preserve'
    record('strict_preserve_has_no_mutations',not report.changes and not report.mutation_ledger and int(repair.get('repair_count',0))==0,strict_preserve)
    failed=[name for name,value in checks.items() if value is False]
    applicable=[value for value in checks.values() if value is not None]
    score=round(100*sum(value is True for value in applicable)/max(1,len(applicable)),1)
    status={name:('N/A' if value is None else ('PASS' if value else 'FAIL')) for name,value in checks.items()}
    technical_pass=not failed
    certification={'technical_pass':technical_pass,'pa800_hardware_verified':False,'musical_listening_verified':False,'hardware_evidence_available':bool((getattr(report,'hardware_evidence',{}) or {}).get('available'))}
    classification='FAIL' if failed else 'TECHNICAL_PASS_PA800_UNVERIFIED'
    return authority,{'schema':'PA800_FINAL_QUALITY_GATE_V2','checks':checks,'check_status':status,'failed_checks':failed,'applicable_checks':len(applicable),'not_applicable_checks':sum(value is None for value in checks.values()),'score_percent':score,'classification':classification,'certification':certification,'pass':technical_pass,'neural_factory_boundary':neural_boundary,'limits':{'minimum_velocity_iqr_retention':minimum_iqr,'insert_master_fx_authorized':False,'harmony_pitch_rewrite_authorized':False,'pa800_hardware_certification_claimed':False,'musical_listening_certification_claimed':False}}
