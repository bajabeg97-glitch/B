"""Validate runtime Factory artifacts and optionally write a SHA-256 manifest."""
from __future__ import annotations
import argparse,hashlib,json,os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'pa800_optimizer'/'profiles'/'data'
REQUIRED={
    'factory_sound_profiles_v1.json':('profiles',542),
    'factory_drum_key_profiles_v1.json':('profiles',2004),
    'factory_velocity_semantics_v2.json':('parent_profiles',542),
    'factory_atomic_max_summary.json':('styles',252),
    'factory_profile_stability_v1.json':('profiles',148),
    'pa800_dnc_manual_registry_v1.json':('sounds',23),
    'instrument_family_positive_models_v1.json':('allowed',5),
    'rare_family_evidence_v1.json':('eligible_auto_profiles',0),
    'pa800_profile_semantics_sources_v1.json':('official_sources',3),
    'factory_profile_completeness_v1.json':('cards',565),
    'exact_instrument_neural_profiles_v1.json':('profiles',565),
}
ROOT_REQUIRED={
    'PUBLIC_API_STRESS_MANIFEST.json':('public_functions',None),
    'INSTRUMENT_INTENT_STRESS_MANIFEST.json':('midi_case_count',110),
    'INSTRUMENT_INTENT_STRESS_RESULT.json':('passed_cases',110),
    'FAMILY_INTENT_STRESS_RESULT.json':('passed_cases',38),
    'SECTION_NARRATIVE_STRESS_MANIFEST.json':('midi_case_count',24),
    'SECTION_NARRATIVE_STRESS_RESULT.json':('passed_cases',24),
    'INSTRUMENT_INTENT_GROUND_TRUTH_STATUS.json':('status','EXTERNAL_REQUIRED'),
    'NEURAL_DATASET_CERTIFICATION_RESULT.json':('dataset_cases',60),
    'NEURAL_ENCODER_CERTIFICATION_RESULT.json':('sources',14),
    'INSTRUMENT_PROFILE_CERTIFICATION_RESULT.json':('profiles',565),
}

def sha256(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def main(argv=None):
    ap=argparse.ArgumentParser();ap.add_argument('--write-manifest',action='store_true');ap.add_argument('--require-rebuild-corpus',action='store_true');ns=ap.parse_args(argv)
    rows=[];errors=[]
    for name,(key,expected) in REQUIRED.items():
        path=DATA/name
        if not path.exists():errors.append('missing '+name);continue
        if path.stat().st_size==0:errors.append('empty '+name);continue
        try:raw=json.loads(path.read_text(encoding='utf-8'))
        except Exception as exc:errors.append('invalid_json %s: %s' % (name,exc));continue
        value=len(raw.get(key,[])) if isinstance(raw.get(key),list) else raw.get(key)
        if expected is None:
            if not isinstance(value,int) or value<235:errors.append(f'{name}:{key} expected >=235, got {value}')
        elif value!=expected:errors.append(f'{name}:{key} expected {expected}, got {value}')
        rows.append({'path':str(path.relative_to(ROOT)).replace('\\','/'),'bytes':path.stat().st_size,'sha256':sha256(path),'check':{key:value}})
    for name,(key,expected) in ROOT_REQUIRED.items():
        path=ROOT/name
        if not path.exists():errors.append('missing '+name);continue
        if path.stat().st_size==0:errors.append('empty '+name);continue
        try:raw=json.loads(path.read_text(encoding='utf-8'))
        except Exception as exc:errors.append('invalid_json %s: %s' % (name,exc));continue
        value=(raw.get('inventory') or {}).get(key) if name=='PUBLIC_API_STRESS_MANIFEST.json' else raw.get(key)
        if expected is None:
            if not isinstance(value,int) or value<235:errors.append(f'{name}:{key} expected >=235, got {value}')
        elif value!=expected:errors.append(f'{name}:{key} expected {expected}, got {value}')
        rows.append({'path':str(path.relative_to(ROOT)).replace('\\','/'),'bytes':path.stat().st_size,'sha256':sha256(path),'check':{key:value}})
    stress_path=ROOT/'COMPLETE_STRESS_RESULT.json'
    stress_running=os.environ.get('PA800_COMPLETE_STRESS_RUNNING')=='1'
    if stress_running:pass
    elif not stress_path.exists() or stress_path.stat().st_size==0:errors.append('missing_or_empty COMPLETE_STRESS_RESULT.json')
    else:
        try:stress=json.loads(stress_path.read_text(encoding='utf-8'))
        except Exception as exc:errors.append('invalid_json COMPLETE_STRESS_RESULT.json: %s' % exc);stress={}
        if stress:
            if stress.get('pass') is not True:errors.append('COMPLETE_STRESS_RESULT.json:pass expected true')
            expected_functions=((json.loads((ROOT/'PUBLIC_API_STRESS_MANIFEST.json').read_text(encoding='utf-8')).get('inventory') or {}).get('public_functions'))
            if stress.get('accounted_functions')!=expected_functions:errors.append(f"COMPLETE_STRESS_RESULT.json:accounted_functions expected {expected_functions}, got {stress.get('accounted_functions')}")
            if stress.get('unaccounted_functions')!=0:errors.append(f"COMPLETE_STRESS_RESULT.json:unaccounted_functions expected 0, got {stress.get('unaccounted_functions')}")
    corpus=ROOT/'corpus'/'Factory Styles.zip'
    if corpus.exists() and corpus.stat().st_size:
        rows.append({'path':str(corpus.relative_to(ROOT)).replace('\\','/'),'bytes':corpus.stat().st_size,'sha256':sha256(corpus)})
    elif ns.require_rebuild_corpus:errors.append('missing_or_empty corpus/Factory Styles.zip')
    manifest={'schema':'PA800_RELEASE_FACTORY_MANIFEST_V1','files':rows,'errors':errors}
    if ns.write_manifest:(ROOT/'FACTORY_RELEASE_MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(manifest,indent=2))
    return 1 if errors else 0

if __name__=='__main__':raise SystemExit(main())
