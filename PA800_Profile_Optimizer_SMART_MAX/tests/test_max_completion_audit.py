from pathlib import Path

from tools.max_completion_audit import evaluate,render


def test_completion_audit_closes_fx_safely_without_faking_hardware():
    root=Path(__file__).resolve().parents[1];report=evaluate(root)
    assert report['local_max_pass'] and not report['hardware_proven_full']
    assert report['phases']['2.7_fx_serialization']['status']=='CLOSED_RECOMMENDATION_ONLY'
    assert report['phases']['2.4_instrument_models']['status']=='LOCAL_PROXY_PASS'
    assert report['phases']['2.4_instrument_models']['allowed_families']==['BASS','ENSEMBLE','PIANO','REED']
    assert report['phases']['2.4C_rare_families']['status']=='CLOSED_PRESERVE'
    assert report['phases']['2.4D_profile_completeness']['status']=='PASS_EXPLICIT_UNKNOWNS'
    assert report['phases']['2.4E_complete_stress']['status'] in ('PASS','RUNNING')
    assert report['phases']['2.5.0_instrument_intent']['status']=='ANALYZER_STRESS_PASS'
    assert report['phases']['2.5.1_intent_ground_truth']['status']=='INFRASTRUCTURE_PASS_EXTERNAL_DATA'
    assert report['phases']['2.5.2_family_intent']['status']=='LOCAL_PROXY_STRESS_PASS'
    assert report['phases']['2.5.2_family_intent']['passed_cases']==38
    assert report['phases']['2.5.3_section_narrative']['status']=='LOCAL_PROXY_STRESS_PASS'
    assert report['phases']['2.5.3_section_narrative']['passed_cases']==24
    assert report['phases']['3.2_neural_dataset']['status']=='LOCAL_DATASET_INFRASTRUCTURE_PASS'
    assert report['phases']['3.2_neural_dataset']['dataset_cases']==60
    assert report['phases']['3.2_neural_dataset']['hard_negatives']==26
    assert report['phases']['3.2_neural_dataset']['trained_model'] is False
    assert report['phases']['3.3_neural_encoder']['status']=='LOCAL_PROXY_TRAINING_PASS'
    assert report['phases']['3.3_neural_encoder']['trained_model'] is True
    assert report['phases']['3.3_neural_encoder']['production_ready'] is False
    assert report['phases']['3.3_neural_encoder']['test_improvement']>0
    assert report['phases']['3.4_exact_instrument_profiles']['status']=='EXACT_PROFILE_COVERAGE_PASS'
    assert report['phases']['3.4_exact_instrument_profiles']['profiles']==565
    assert report['phases']['3.4_exact_instrument_profiles']['exact_resolved']==565
    assert report['phases']['3.4_exact_instrument_profiles']['production_auto_profiles']==0
    assert report['phases']['2.5_2.6_hardware_dnc']['status']=='EXTERNAL_REQUIRED'
    assert report['phases']['2.9_release_engineering']['status']=='LOCAL_READY'
    text=render(report);assert 'Hardware-Proven FULL: **NO**' in text and 'EXTERNAL_REQUIRED' in text
