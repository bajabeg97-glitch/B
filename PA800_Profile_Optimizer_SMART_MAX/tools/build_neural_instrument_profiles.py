"""Build one exact neural routing profile for every Factory/manual instrument."""
from __future__ import annotations
import argparse,csv,json
from pathlib import Path
from pa800_optimizer.neural.instrument_profiles import build_instrument_profile_catalog,validate_instrument_profile_catalog

ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'pa800_optimizer'/'profiles'/'data'

def render_markdown(catalog):
    summary=catalog['summary'];lines=['# Exact Neural Instrument Profiles V1','',f"Profiles: **{summary['profiles']}/565**",f"Families: **{summary['family_count']}**",f"Protected profiles: **{summary['protected_profiles']}**",f"Grouped proxy profiles: **{summary['grouped_proxy_profiles']}**",f"Production AUTO profiles: **{summary['production_auto_profiles']}**",'','| Family | Profiles |','|---|---:|']
    for family,count in summary['families'].items():lines.append(f'| {family} | {count} |')
    lines+=['','Svaki profil je exact Sound+role kartica. `UNKNOWN` numerika se ne popunjava prosjekom; manual-only DNC, RX/DNC i SFX/Synth FX ostaju preserve.']
    return '\n'.join(lines)+'\n'

def build(output_json,output_csv,output_md):
    catalog=build_instrument_profile_catalog(DATA/'factory_profile_completeness_v1.json',DATA/'instrument_family_positive_models_v1.json',ROOT/'NEURAL_ENCODER_MODEL_3.3.0.json');audit=validate_instrument_profile_catalog(catalog);Path(output_json).write_text(json.dumps(catalog,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    with Path(output_csv).open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['instrument_profile_id','msb','lsb','program','sound','role','family','origin','support_grade','stability','routing','protected','eligible_defects','controller_guards','grouped_proxy_models','unknown_count']);writer.writeheader()
        for row in catalog['profiles']:
            identity=row['identity'];writer.writerow({'instrument_profile_id':row['instrument_profile_id'],'msb':identity.get('msb'),'lsb':identity.get('lsb'),'program':identity.get('program'),'sound':identity.get('sound'),'role':identity.get('role'),'family':row['family'],'origin':row['origin'],'support_grade':(row.get('support') or {}).get('grade'),'stability':row.get('stability'),'routing':row['routing'],'protected':row['protected'],'eligible_defects':'|'.join(row['eligible_defect_suggestions']),'controller_guards':'|'.join(map(str,row['controller_guards'])),'grouped_proxy_models':'|'.join(row['grouped_proxy_models']),'unknown_count':len(row['unresolved'])})
    Path(output_md).write_text(render_markdown(catalog),encoding='utf-8');return catalog,audit

def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--json',default=str(DATA/'exact_instrument_neural_profiles_v1.json'));parser.add_argument('--csv',default=str(ROOT/'EXACT_INSTRUMENT_NEURAL_PROFILES.csv'));parser.add_argument('--markdown',default=str(ROOT/'EXACT_INSTRUMENT_NEURAL_PROFILES.md'));args=parser.parse_args(argv);catalog,audit=build(args.json,args.csv,args.markdown);print(json.dumps({'summary':catalog['summary'],'audit':audit,'catalog_digest':catalog['catalog_digest']},indent=2));return 0 if audit['pass'] else 1

if __name__=='__main__':raise SystemExit(main())