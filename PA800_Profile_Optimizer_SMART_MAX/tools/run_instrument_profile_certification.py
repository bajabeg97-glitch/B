"""Certify exact per-instrument coverage and fail-closed routing."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from pa800_optimizer.neural.instrument_profiles import FAMILY_POLICIES,VECTOR_FIELDS,resolve_instrument_profile,validate_instrument_profile_catalog
from tools.build_neural_instrument_profiles import DATA,ROOT,build

def certify(output):
    catalog,audit=build(DATA/'exact_instrument_neural_profiles_v1.json',ROOT/'EXACT_INSTRUMENT_NEURAL_PROFILES.csv',ROOT/'EXACT_INSTRUMENT_NEURAL_PROFILES.md');exact=0;failures=[]
    for row in catalog['profiles']:
        identity=row['identity'];result=resolve_instrument_profile(catalog,identity.get('msb'),identity.get('lsb'),identity.get('program'),identity.get('sound'),identity.get('role'))
        if result['status']=='EXACT' and result['profile']['instrument_profile_id']==row['instrument_profile_id']:exact+=1
        else:failures.append(row['instrument_profile_id'])
    grouped_addresses={(row['family'],tuple(row['identity'].get(key) for key in ('msb','lsb','program'))) for row in catalog['profiles'] if row['grouped_proxy_models']};manual=[row for row in catalog['profiles'] if row['origin']=='OFFICIAL_MANUAL_ONLY'];sfx=[row for row in catalog['profiles'] if row['family'] in ('SFX','SYNTH_FX')];vector_size=len(VECTOR_FIELDS);checks={'catalog_audit':audit['pass'],'exact_resolution':exact==565 and not failures,'family_coverage':set(catalog['summary']['families'])==set(FAMILY_POLICIES),'manual_only_preserve':len(manual)==23 and all(row['routing']=='PRESERVE' and row['protected'] for row in manual),'sfx_preserve':bool(sfx) and all(row['routing']=='PRESERVE' and not row['eligible_defect_suggestions'] for row in sfx),'grouped_proxy_addresses':len(grouped_addresses)==5,'explicit_embedding_boundary':all(row['encoder']['exact_embedding_status']=='NO_EXACT_PER_INSTRUMENT_PERFORMANCE_PAIR' and row['encoder']['family_prior_only'] for row in catalog['profiles']),'evidence_vectors':all(len(row['evidence_vector'])==vector_size and len(row['evidence_mask'])==vector_size for row in catalog['profiles']),'no_production_auto':catalog['summary']['production_auto_profiles']==0,'authority':catalog['authority_granted'] is False and all(row['authority_granted'] is False and row['mutations']==0 for row in catalog['profiles'])}
    report={'schema':'PA800_EXACT_INSTRUMENT_PROFILE_CERTIFICATION_V1','release':'3.4.0-alpha1','profiles':catalog['summary']['profiles'],'factory_profiles':catalog['summary']['factory_profiles'],'manual_only_profiles':catalog['summary']['manual_only_profiles'],'families':catalog['summary']['family_count'],'family_counts':catalog['summary']['families'],'protected_profiles':catalog['summary']['protected_profiles'],'suggestion_profiles':catalog['summary']['suggestion_profiles'],'grouped_proxy_profiles':catalog['summary']['grouped_proxy_profiles'],'exact_resolved':exact,'resolution_failures':failures,'catalog_digest':catalog['catalog_digest'],'encoder_model_digest':catalog['model_digest'],'checks':checks,'production_auto_profiles':0,'mutations':0,'authority_granted':False,'pass':all(checks.values())};Path(output).write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');return report

def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--output',default=str(ROOT/'INSTRUMENT_PROFILE_CERTIFICATION_RESULT.json'));args=parser.parse_args(argv);report=certify(args.output);print(json.dumps(report,indent=2));return 0 if report['pass'] else 1

if __name__=='__main__':raise SystemExit(main())
