"""Compute truthful roadmap completion from evidence artifacts, not prose."""
from __future__ import annotations

import argparse
import csv
import json
import os
import platform
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]


def _json(path,default=None):
    try:return json.loads(path.read_text(encoding='utf-8-sig'))
    except Exception:return {} if default is None else default


def _ground_truth(root):
    rows=[]
    for path in root.rglob('*.json'):
        if path.name=='context_ground_truth_template.json' or 'validation_results' in path.parts:continue
        data=_json(path)
        if isinstance(data,dict) and data.get('schema')=='PA800_CONTEXT_GROUND_TRUTH_V1' and data.get('annotator') and data.get('tracks'):rows.append(data)
    counts={kind:sum(str(row.get('content_type','')).lower()==kind for row in rows) for kind in ('song','style','kar')}
    required={'song':100,'style':100,'kar':30};passed=all(counts[key]>=value for key,value in required.items())
    return {'status':'PASS' if passed else 'EXTERNAL_REQUIRED','counts':counts,'required':required,'files':len(rows),'reason':None if passed else 'Ručno označeni privatni korpus nije dostupan u projektu.'}


def _hardware(root):
    path=root/'PA800_HARDWARE_CAMPAIGN_2.5'/'RESULTS.csv';rows=[]
    if path.is_file():
        with path.open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
    completed=[row for row in rows if str(row.get('status','')).upper() in ('PASS','FAIL')]
    dnc=[row for row in rows if str(row.get('kind','')).lower()=='dnc'];dnc_completed=[row for row in dnc if str(row.get('status','')).upper() in ('PASS','FAIL')]
    return {'status':'PASS' if rows and len(completed)==len(rows) and len(dnc_completed)>=23 else 'EXTERNAL_REQUIRED','rows':len(rows),'completed':len(completed),'dnc_rows':len(dnc),'dnc_completed':len(dnc_completed),'reason':'Za E3 su potrebni fizički Pa800 i popunjeni audio/DNC rezultati.'}


def _fx(root):
    data=_json(root/'FX_SERIALIZATION_EVIDENCE.json');confirmed=bool(data.get('insert_master_fx_schema_confirmed'));auto=bool(data.get('automatic_insert_master_rewrite'))
    safe_closed=(not confirmed and not auto and data.get('unknown_sysex_preserved') is True)
    status='PASS_HARDWARE_SERIALIZATION' if confirmed and auto else ('CLOSED_RECOMMENDATION_ONLY' if safe_closed else 'FAIL_UNSAFE_OR_AMBIGUOUS')
    return {'status':status,'insert_master_confirmed':confirmed,'automatic_rewrite':auto,'existing_cc91_cc93_only':bool(data.get('automatic_existing_cc91_cc93_contour_offset')),'reason':'Insert/Master ostaje trajno recommendation-only.' if safe_closed else None}


def _compatibility(root):
    from tools.compatibility_matrix import collect_reports,evaluate as evaluate_matrix
    identity=_json(root/'BUILD_ID.json');matrix=evaluate_matrix(collect_reports([root/'validation_results',root/'prism-uploads']),identity.get('build_id'),identity.get('version'))
    return {'status':matrix['status'],'reports_seen':matrix['reports_seen'],'reports_eligible':matrix['reports_eligible'],'python_versions':matrix['python_versions'],'windows_generations':matrix['windows_generations'],**matrix['counts'],'unique_input_hashes':matrix['unique_input_hashes'],'required':matrix['required']}


def _release(root):
    required=['constraints-core.txt','constraints-validation.txt','CI_RELEASE_MATRIX.yml','tools/clean_install_smoke.py','tools/build_windows_revalidation.py','tools/sync_ci_workflow.py','tools/compatibility_matrix.py','tools/build_profile_completeness.py','tools/public_api_stress.py','tools/public_api_trace_plugin.py','tools/run_complete_stress.py','tools/instrument_intent_stress_midis.py','tools/evaluate_instrument_intent_stress.py','tools/evaluate_family_intent_stress.py','tools/section_narrative_stress_midis.py','tools/evaluate_section_narrative_stress.py','tools/create_instrument_intent_ground_truth.py','tools/evaluate_instrument_intent_ground_truth.py','tools/forge_neural_dataset.py','tools/audit_neural_dataset.py','tools/run_neural_dataset_certification.py','tools/train_neural_encoder.py','tools/run_neural_encoder_certification.py','tools/build_neural_instrument_profiles.py','tools/run_instrument_profile_certification.py']
    present={name:(root/name).is_file() for name in required}
    return {'status':'LOCAL_READY' if all(present.values()) else 'MISSING','files':present,'execution_gate':'CI/Windows run required'}


def _complete_stress(root):
    manifest=_json(root/'PUBLIC_API_STRESS_MANIFEST.json');inventory=manifest.get('inventory',{})
    manifest_ok=inventory.get('public_functions',0)>=235 and inventory.get('modules',0)>=65 and inventory.get('unclassified')==0
    result_path=root/'COMPLETE_STRESS_RESULT.json';result=_json(result_path) if result_path.is_file() else {}
    if os.environ.get('PA800_COMPLETE_STRESS_RUNNING')=='1' and manifest_ok:status='RUNNING'
    elif not manifest_ok:status='MISSING_OR_UNSAFE'
    elif not result:status='MANIFEST_READY'
    elif result.get('pass') and result.get('accounted_functions')==inventory.get('public_functions') and result.get('unaccounted_functions')==0 and result.get('dynamic_hit_ratio',0)>=.50:status='PASS'
    else:status='FAIL'
    return {'status':status,'declared_minimum':{'public_functions':235,'modules':65},'inventory':inventory,'dynamic_hits':result.get('dynamic_hits'),'dynamic_hit_ratio':result.get('dynamic_hit_ratio'),'accounted_functions':result.get('accounted_functions'),'unaccounted_functions':result.get('unaccounted_functions')}


def _instrument_models(root):
    holdout=_json(root/'INSTRUMENT_FAMILY_HOLDOUT_2.4.json');models=_json(root/'pa800_optimizer'/'profiles'/'data'/'instrument_family_positive_models_v1.json')
    allowed=models.get('allowed',[]) if isinstance(models,dict) else [];families=holdout.get('families',{}) if isinstance(holdout,dict) else {}
    gated={(str(row.get('family')).upper(),tuple(row.get('address') or ())) for row in allowed}
    expected={('PIANO',(121,3,0)),('BASS',(121,7,33)),('ENSEMBLE',(121,2,50)),('ENSEMBLE',(121,5,48)),('REED',(121,1,71))}
    denied=('GUITAR','ORGAN','BRASS','ACCORDION_REED','SYNTH_PAD');denied_pass={family:int((families.get(family) or {}).get('proxy_pass',-1)) for family in denied}
    passed=expected==gated and all(value==0 for value in denied_pass.values()) and holdout.get('authority_granted') is False
    return {'status':'LOCAL_PROXY_PASS' if passed else 'MISSING_OR_UNSAFE','allowed_models':len(allowed),'allowed_families':sorted({family for family,_address in gated}),'denied_family_proxy_pass':denied_pass,'authority_granted':holdout.get('authority_granted'),'hardware_gate':'EXTERNAL_REQUIRED'}


def _rare_families(root):
    data=_json(root/'pa800_optimizer'/'profiles'/'data'/'rare_family_evidence_v1.json')
    closed=data.get('status')=='CLOSED_PRESERVE_NO_ELIGIBLE_PROFILE' and data.get('authority_granted') is False and not data.get('eligible_auto_profiles') and all((data.get('exact_only_policy_checks') or {}).values()) and all((data.get('permanent_preserve_checks') or {}).values())
    return {'status':'CLOSED_PRESERVE' if closed else 'MISSING_OR_UNSAFE','eligible_auto_profiles':len(data.get('eligible_auto_profiles') or []),'authority_granted':data.get('authority_granted'),'policy_checks':data.get('exact_only_policy_checks',{}),'permanent_preserve_checks':data.get('permanent_preserve_checks',{})}


def _profile_completeness(root):
    data=_json(root/'pa800_optimizer'/'profiles'/'data'/'factory_profile_completeness_v1.json');summary=data.get('summary',{})
    passed=summary.get('factory_profiles')==542 and summary.get('manual_dnc_profiles')==23 and summary.get('cards_total')==565 and summary.get('complete_cards')==565 and summary.get('community_authority_cards')==0
    return {'status':'PASS_EXPLICIT_UNKNOWNS' if passed else 'MISSING_OR_UNSAFE','factory_profiles':summary.get('factory_profiles'),'manual_only_profiles':summary.get('manual_only_profiles'),'cards_total':summary.get('cards_total'),'complete_cards':summary.get('complete_cards'),'community_authority_cards':summary.get('community_authority_cards'),'exact_dnc_factory_matches':summary.get('exact_dnc_factory_matches')}


def _instrument_intent(root):
    manifest=_json(root/'INSTRUMENT_INTENT_STRESS_MANIFEST.json');result=_json(root/'INSTRUMENT_INTENT_STRESS_RESULT.json')
    passed=manifest.get('scenario_count')==55 and manifest.get('midi_case_count')==110 and result.get('pass') is True and result.get('passed_cases')==110 and result.get('failed_cases')==0 and result.get('pair_separation_passed')==55 and result.get('mutations')==0 and result.get('authority_granted') is False
    return {'status':'ANALYZER_STRESS_PASS' if passed else 'MISSING_OR_UNSAFE','schema':'PA800_INSTRUMENT_INTENT_V3','scenarios':manifest.get('scenario_count'),'midi_cases':manifest.get('midi_case_count'),'passed_cases':result.get('passed_cases'),'pair_separation_passed':result.get('pair_separation_passed'),'mutations':result.get('mutations'),'authority_granted':result.get('authority_granted'),'ground_truth_gate':'EXTERNAL_REQUIRED'}


def _intent_ground_truth(root):
    data=_json(root/'INSTRUMENT_INTENT_GROUND_TRUTH_STATUS.json');gate=data.get('calibration_gate',{})
    safe=data.get('schema')=='PA800_INSTRUMENT_INTENT_GROUND_TRUTH_EVALUATION_V2' and data.get('status') in ('EXTERNAL_REQUIRED','PASS') and data.get('authority_granted') is False and data.get('mutations')==0 and gate.get('may_grant_mutation_authority') is False and gate.get('authority_granted') is False
    status='INFRASTRUCTURE_PASS_EXTERNAL_DATA' if safe and data.get('status')=='EXTERNAL_REQUIRED' else ('PASS' if safe and data.get('status')=='PASS' else 'MISSING_OR_UNSAFE')
    return {'status':status,'file_counts':data.get('file_counts',{}),'required_file_counts':data.get('required_file_counts',{}),'coverage_complete':data.get('coverage_complete'),'fine_macro_f1':(data.get('fine_roles') or {}).get('macro_f1'),'superclass_macro_f1':(data.get('superclasses') or {}).get('macro_f1'),'unknown_precision':data.get('unknown_precision'),'ece':(data.get('calibration') or {}).get('ece'),'may_grant_mutation_authority':gate.get('may_grant_mutation_authority')}


def _family_intent(root):
    data=_json(root/'FAMILY_INTENT_STRESS_RESULT.json')
    passed=data.get('schema')=='PA800_FAMILY_INTENT_STRESS_RESULT_V1' and data.get('pass') is True and data.get('midi_case_count')==38 and data.get('passed_cases')==38 and data.get('failed_cases')==0 and data.get('scenario_count')==19 and data.get('pair_separation_passed')==19 and data.get('mutations')==0 and data.get('authority_granted') is False
    return {'status':'LOCAL_PROXY_STRESS_PASS' if passed else 'MISSING_OR_UNSAFE','schema':'PA800_FAMILY_INTENT_V1','midi_cases':data.get('midi_case_count'),'passed_cases':data.get('passed_cases'),'scenario_pairs':data.get('scenario_count'),'pair_separation_passed':data.get('pair_separation_passed'),'mutations':data.get('mutations'),'authority_granted':data.get('authority_granted'),'ground_truth_gate':'EXTERNAL_REQUIRED'}


def _section_narrative(root):
    manifest=_json(root/'SECTION_NARRATIVE_STRESS_MANIFEST.json');data=_json(root/'SECTION_NARRATIVE_STRESS_RESULT.json')
    passed=manifest.get('scenario_count')==12 and manifest.get('midi_case_count')==24 and data.get('schema')=='PA800_SECTION_NARRATIVE_STRESS_RESULT_V1' and data.get('pass') is True and data.get('passed_cases')==24 and data.get('failed_cases')==0 and data.get('pair_separation_passed')==12 and data.get('mutations')==0 and data.get('authority_granted') is False
    return {'status':'LOCAL_PROXY_STRESS_PASS' if passed else 'MISSING_OR_UNSAFE','schema':'PA800_SECTION_NARRATIVE_V3','scenarios':manifest.get('scenario_count'),'midi_cases':data.get('midi_case_count'),'passed_cases':data.get('passed_cases'),'pair_separation_passed':data.get('pair_separation_passed'),'mutations':data.get('mutations'),'authority_granted':data.get('authority_granted'),'ground_truth_gate':'EXTERNAL_REQUIRED'}


def _neural_dataset(root):
    data=_json(root/'NEURAL_DATASET_CERTIFICATION_RESULT.json');checks=data.get('checks',{});audit=data.get('dataset_audit',{});types=set(data.get('corruption_types') or [])
    expected={'ONSET_SPIKE','GATE_TRUNCATE','GATE_OVERLAP','DUPLICATE_HIT','CHORD_DESYNC','GROOVE_DRIFT'}
    passed=data.get('schema')=='PA800_NEURAL_DATASET_CERTIFICATION_V2' and data.get('pass') is True and data.get('sources')==14 and data.get('roundtrip_passed')==14 and data.get('dataset_cases',0)>=50 and data.get('hard_negatives')==26 and data.get('protected_only_sources')==2 and types==expected and checks and all(checks.values()) and audit.get('pass') is True and not audit.get('group_split_leakage') and data.get('mutations_to_original_sources')==0 and data.get('authority_granted') is False and data.get('trained_model') is False
    return {'status':'LOCAL_DATASET_INFRASTRUCTURE_PASS' if passed else 'MISSING_OR_UNSAFE','schema':'PA800_NEURAL_DATASET_V2','sources':data.get('sources'),'roundtrip_passed':data.get('roundtrip_passed'),'dataset_cases':data.get('dataset_cases'),'hard_negatives':data.get('hard_negatives'),'protected_only_sources':data.get('protected_only_sources'),'corruption_types':sorted(types),'dataset_digest':data.get('dataset_digest'),'group_split_leakage':audit.get('group_split_leakage'),'mutations_to_original_sources':data.get('mutations_to_original_sources'),'authority_granted':data.get('authority_granted'),'trained_model':False,'licensed_real_corpus':'EXTERNAL_REQUIRED'}


def _neural_encoder(root):
    data=_json(root/'NEURAL_ENCODER_CERTIFICATION_RESULT.json');checks=data.get('checks',{});metrics=(data.get('evaluation') or {}).get('metrics',{})
    passed=data.get('schema')=='PA800_NEURAL_ENCODER_CERTIFICATION_V1' and data.get('pass') is True and data.get('sources')==14 and data.get('unique_source_groups')==13 and data.get('split_groups')=={'train':9,'validation':2,'test':2} and checks and all(checks.values()) and (metrics.get('validation') or {}).get('improvement',0)>0 and (metrics.get('test') or {}).get('improvement',0)>0 and data.get('transposition_cosine',0)>=.999999 and data.get('trained_model') is True and data.get('production_ready') is False and data.get('mutations')==0 and data.get('authority_granted') is False
    return {'status':'LOCAL_PROXY_TRAINING_PASS' if passed else 'MISSING_OR_UNSAFE','schema':'PA800_SELF_SUPERVISED_ENCODER_V1','sources':data.get('sources'),'unique_source_groups':data.get('unique_source_groups'),'split_groups':data.get('split_groups'),'model_digest':data.get('model_digest'),'hidden_size':data.get('hidden_size'),'epochs':data.get('epochs'),'validation_improvement':(metrics.get('validation') or {}).get('improvement'),'test_improvement':(metrics.get('test') or {}).get('improvement'),'transposition_cosine':data.get('transposition_cosine'),'trained_model':data.get('trained_model'),'production_ready':data.get('production_ready'),'mutations':data.get('mutations'),'authority_granted':data.get('authority_granted'),'licensed_real_corpus':'EXTERNAL_REQUIRED'}


def _exact_instrument_profiles(root):
    data=_json(root/'INSTRUMENT_PROFILE_CERTIFICATION_RESULT.json');checks=data.get('checks',{})
    passed=data.get('schema')=='PA800_EXACT_INSTRUMENT_PROFILE_CERTIFICATION_V1' and data.get('pass') is True and data.get('profiles')==565 and data.get('factory_profiles')==542 and data.get('manual_only_profiles')==23 and data.get('families')==18 and data.get('exact_resolved')==565 and checks and all(checks.values()) and data.get('production_auto_profiles')==0 and data.get('mutations')==0 and data.get('authority_granted') is False
    return {'status':'EXACT_PROFILE_COVERAGE_PASS' if passed else 'MISSING_OR_UNSAFE','schema':'PA800_EXACT_INSTRUMENT_NEURAL_PROFILES_V1','profiles':data.get('profiles'),'factory_profiles':data.get('factory_profiles'),'manual_only_profiles':data.get('manual_only_profiles'),'families':data.get('families'),'family_counts':data.get('family_counts'),'protected_profiles':data.get('protected_profiles'),'suggestion_profiles':data.get('suggestion_profiles'),'grouped_proxy_profiles':data.get('grouped_proxy_profiles'),'exact_resolved':data.get('exact_resolved'),'catalog_digest':data.get('catalog_digest'),'production_auto_profiles':data.get('production_auto_profiles'),'mutations':data.get('mutations'),'authority_granted':data.get('authority_granted'),'exact_per_instrument_embeddings':'EXTERNAL_REQUIRED'}


def evaluate(root=ROOT):
    root=Path(root);phases={'2.3_ground_truth':_ground_truth(root),'2.4_instrument_models':_instrument_models(root),'2.4C_rare_families':_rare_families(root),'2.4D_profile_completeness':_profile_completeness(root),'2.4E_complete_stress':_complete_stress(root),'2.5.0_instrument_intent':_instrument_intent(root),'2.5.1_intent_ground_truth':_intent_ground_truth(root),'2.5.2_family_intent':_family_intent(root),'2.5.3_section_narrative':_section_narrative(root),'2.5_2.6_hardware_dnc':_hardware(root),'2.7_fx_serialization':_fx(root),'2.8_compatibility':_compatibility(root),'2.9_release_engineering':_release(root),'3.2_neural_dataset':_neural_dataset(root),'3.3_neural_encoder':_neural_encoder(root),'3.4_exact_instrument_profiles':_exact_instrument_profiles(root)}
    unsafe=phases['2.4_instrument_models']['status']!='LOCAL_PROXY_PASS' or phases['2.4C_rare_families']['status']!='CLOSED_PRESERVE' or phases['2.4D_profile_completeness']['status']!='PASS_EXPLICIT_UNKNOWNS' or phases['2.4E_complete_stress']['status'] in ('MISSING_OR_UNSAFE','FAIL') or phases['2.5.0_instrument_intent']['status']!='ANALYZER_STRESS_PASS' or phases['2.5.1_intent_ground_truth']['status']=='MISSING_OR_UNSAFE' or phases['2.5.2_family_intent']['status']!='LOCAL_PROXY_STRESS_PASS' or phases['2.5.3_section_narrative']['status']!='LOCAL_PROXY_STRESS_PASS' or phases['2.7_fx_serialization']['status']=='FAIL_UNSAFE_OR_AMBIGUOUS' or phases['2.9_release_engineering']['status']=='MISSING' or phases['3.2_neural_dataset']['status']!='LOCAL_DATASET_INFRASTRUCTURE_PASS' or phases['3.3_neural_encoder']['status']!='LOCAL_PROXY_TRAINING_PASS' or phases['3.4_exact_instrument_profiles']['status']!='EXACT_PROFILE_COVERAGE_PASS'
    return {'schema':'PA800_MAX_COMPLETION_AUDIT_V1','generated_on':'2026-08-25','host_python':platform.python_version(),'local_max_pass':not unsafe,'hardware_proven_full':all(row.get('status') in ('PASS','PASS_HARDWARE_SERIALIZATION') for row in phases.values()),'phases':phases}


def render(report):
    lines=['# MAX Completion Ledger','',f"Local maximum: **{'PASS' if report['local_max_pass'] else 'FAIL'}**",f"Hardware-Proven FULL: **{'YES' if report['hardware_proven_full'] else 'NO'}**",'','| Phase | Computed status |','|---|---|']
    for name,row in report['phases'].items():lines.append(f"| {name} | {row['status']} |")
    lines+=['','`EXTERNAL_REQUIRED` nije softverski kvar: znači da dokaz zahtijeva privatni označeni korpus, Windows matricu ili fizički Pa800.']
    return '\n'.join(lines)+'\n'


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--json',default='MAX_COMPLETION_LEDGER.json');parser.add_argument('--markdown',default='MAX_COMPLETION_LEDGER.md');args=parser.parse_args(argv);report=evaluate();Path(args.json).write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8');Path(args.markdown).write_text(render(report),encoding='utf-8');print(json.dumps(report,indent=2,ensure_ascii=False));return 0 if report['local_max_pass'] else 1


if __name__=='__main__':raise SystemExit(main())
