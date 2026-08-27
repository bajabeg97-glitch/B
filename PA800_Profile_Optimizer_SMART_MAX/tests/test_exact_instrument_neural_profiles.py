import copy,json
from pathlib import Path
from pa800_optimizer.neural.instrument_profiles import FAMILY_POLICIES,build_instrument_profile_catalog,resolve_instrument_profile,validate_instrument_profile_catalog

ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'pa800_optimizer'/'profiles'/'data'

def _catalog():return build_instrument_profile_catalog(DATA/'factory_profile_completeness_v1.json',DATA/'instrument_family_positive_models_v1.json',ROOT/'NEURAL_ENCODER_MODEL_3.3.0.json')

def test_every_instrument_has_one_complete_exact_profile():
    catalog=_catalog();audit=validate_instrument_profile_catalog(catalog);assert audit['pass'];assert catalog['summary']['profiles']==565 and catalog['summary']['factory_profiles']==542 and catalog['summary']['manual_only_profiles']==23;assert set(catalog['summary']['families'])==set(FAMILY_POLICIES)

def test_every_profile_resolves_by_full_identity():
    catalog=_catalog()
    for row in catalog['profiles']:
        identity=row['identity'];result=resolve_instrument_profile(catalog,identity['msb'],identity['lsb'],identity['program'],identity['sound'],identity['role']);assert result['status']=='EXACT' and result['profile']['instrument_profile_id']==row['instrument_profile_id']

def test_manual_dnc_and_sfx_are_fail_closed():
    catalog=_catalog();manual=[row for row in catalog['profiles'] if row['origin']=='OFFICIAL_MANUAL_ONLY'];sfx=[row for row in catalog['profiles'] if row['family'] in ('SFX','SYNTH_FX')];assert len(manual)==23 and sfx;assert all(row['protected'] and row['routing']=='PRESERVE' and not row['production_auto'] for row in manual+sfx)

def test_profiles_keep_unknowns_and_do_not_fake_exact_embeddings():
    catalog=_catalog();assert any(row['unresolved'] for row in catalog['profiles']);assert all(row['encoder']['exact_embedding_status']=='NO_EXACT_PER_INSTRUMENT_PERFORMANCE_PAIR' for row in catalog['profiles']);assert catalog['summary']['exact_embeddings']==0

def test_catalog_tamper_is_rejected():
    catalog=_catalog();bad=copy.deepcopy(catalog);bad['profiles'][0]['authority_granted']=True;assert not validate_instrument_profile_catalog(bad)['pass']