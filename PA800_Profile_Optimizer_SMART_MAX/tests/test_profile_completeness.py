import json
from pathlib import Path

from pa800_optimizer.profiles.registry import ProfileRegistry
from tools.build_profile_completeness import build


ROOT=Path(__file__).resolve().parents[1]


def test_every_factory_and_manual_profile_has_complete_explicit_schema():
    result=build();summary=result['summary']
    assert summary['factory_profiles']==542 and summary['manual_dnc_profiles']==23
    assert summary['cards_total']==565 and summary['complete_cards']==565
    assert summary['manual_only_profiles']==23 and summary['exact_dnc_factory_matches']==0
    assert summary['community_authority_cards']==0
    assert all((row['factory_profile'] is not None)==(row['origin']=='FACTORY_CORPUS') for row in result['cards'])


def test_missing_factory_measurements_are_unknown_not_fabricated():
    result=build();factory=[row for row in result['cards'] if row['origin']=='FACTORY_CORPUS']
    gate_unknown=[row for row in factory if row['factory_evidence']['gate_to_next_onset']['status']=='UNKNOWN_NOT_OBSERVED']
    controller_empty=[row for row in factory if row['factory_evidence']['controllers']['status']=='OBSERVED_EMPTY']
    assert len(gate_unknown)==7 and len(controller_empty)==313
    assert all('gate_to_next_onset' in row['unresolved'] for row in gate_unknown)
    assert all(row['authority']['community_mutation'] is False for row in result['cards'])


def test_manual_only_dnc_cards_preserve_factory_unknowns_and_hardware_gate():
    result=build();manual=[row for row in result['cards'] if row['origin']=='OFFICIAL_MANUAL_ONLY']
    assert len(manual)==23
    assert all(row['factory_evidence']['velocity']['status']=='NO_FACTORY_PROFILE' for row in manual)
    assert all('audible_articulation_result' in row['unresolved'] for row in manual)
    assert all(row['authority']=={'factory_numeric':False,'manual_mutation':False,'community_mutation':False,'hardware_confirmed':False} for row in manual)


def test_source_registry_keeps_every_forum_claim_non_authoritative():
    data=json.loads((ROOT/'pa800_optimizer'/'profiles'/'data'/'pa800_profile_semantics_sources_v1.json').read_text(encoding='utf-8'))
    assert len(data['official_sources'])==3 and len(data['community_sources'])==4
    assert all(row['authority'] is False for row in data['community_sources'])


def test_runtime_registry_exposes_factory_and_manual_only_cards():
    registry=ProfileRegistry();card=registry.profile_completeness(registry.profiles[0])
    assert card['completion_state']=='COMPLETE_WITH_EXPLICIT_UNKNOWNS'
    assert len(registry.profile_completeness_cards)==565
    assert len(registry.manual_only_profiles())==23