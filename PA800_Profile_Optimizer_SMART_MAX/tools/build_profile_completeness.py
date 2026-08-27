"""Build evidence-complete cards for every Factory and manual-only profile.

Completeness means every semantic field is present and every missing fact is
explicitly UNKNOWN.  It never fabricates a Factory distribution.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'pa800_optimizer'/'profiles'/'data'
FACTORY_FIELDS=('velocity','velocity_modes','key','pitch_clusters','primary_pitch_cluster','special_pitch_candidates','duration_ticks','gate_to_next_onset','notes_per_bar','exact_onset_chord_size','signed_interval','timing_residual_ticks','roles','cvs','elements','controllers')
ALWAYS_UNKNOWN=('internal_oscillator_routing','exact_multisample_identity','audible_timbre_result','insert_master_fx_serialization')


def _norm(value):return ' '.join(str(value or '').lower().split())


def _profile_id(identity):
    raw='|'.join(str(identity.get(key,'')) for key in ('msb','lsb','program','sound','role','org_family'))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]


def _field_state(value):
    if value is None:return 'UNKNOWN_NOT_OBSERVED'
    if value=={} or value==[]:return 'OBSERVED_EMPTY'
    return 'OBSERVED'


def build(factory=None,stability=None,dnc=None,sources=None):
    factory=factory or json.loads((DATA/'factory_sound_profiles_v1.json').read_text(encoding='utf-8'))
    stability=stability or json.loads((DATA/'factory_profile_stability_v1.json').read_text(encoding='utf-8'))
    dnc=dnc or json.loads((DATA/'pa800_dnc_manual_registry_v1.json').read_text(encoding='utf-8'))
    sources=sources or json.loads((DATA/'pa800_profile_semantics_sources_v1.json').read_text(encoding='utf-8'))
    stable={}
    for row in stability.get('profiles',[]):
        identity=row.get('identity',{});stable[(identity.get('msb'),identity.get('lsb'),identity.get('program'),_norm(identity.get('sound')))]=row.get('stability','UNKNOWN')
    dnc_by_key={(row['msb'],row['lsb'],row['program'],_norm(row['name'])):row for row in dnc.get('sounds',[])}
    family_semantics=sources.get('family_semantics',{});cards=[];field_counts=Counter();matched=set()
    for profile in factory.get('profiles',[]):
        identity=profile.get('identity',{});family=str(identity.get('org_family') or 'UNKNOWN').upper();address=[identity.get('msb'),identity.get('lsb'),identity.get('program')]
        exact=dnc_by_key.get((*address,_norm(identity.get('sound'))))
        if exact:matched.add((*address,_norm(identity.get('sound'))))
        evidence={field:{'status':_field_state(profile.get(field)),'source':'factory_corpus'} for field in FACTORY_FIELDS}
        for field,row in evidence.items():field_counts[(field,row['status'])]+=1
        unresolved=[field for field,row in evidence.items() if row['status']!='OBSERVED']+list(ALWAYS_UNKNOWN)
        if exact:unresolved+=['exact_trigger_context_on_hardware','audible_articulation_result']
        card={
            'profile_id':_profile_id(identity),'origin':'FACTORY_CORPUS','identity':identity,'support':profile.get('support',{}),'factory_profile':profile,
            'stability':stable.get((*address,_norm(identity.get('sound'))),'UNKNOWN'),'factory_evidence':evidence,
            'official_manual':{'exact_dnc':exact,'family_semantics':family_semantics.get(family,{'guards':['no_family_manual_mapping'],'manual_scope':'unknown'})},
            'community':{'candidates':family_semantics.get(family,{}).get('community_candidates',[]),'authority':False},
            'unresolved':sorted(set(unresolved)),
            'authority':{'factory_numeric':True,'manual_mutation':False,'community_mutation':False,'hardware_confirmed':False},
            'completion_state':'COMPLETE_WITH_EXPLICIT_UNKNOWNS'
        }
        cards.append(card)
    manual_only=[]
    for row in dnc.get('sounds',[]):
        key=(row['msb'],row['lsb'],row['program'],_norm(row['name']))
        if key in matched:continue
        identity={'msb':row['msb'],'lsb':row['lsb'],'program':row['program'],'sound':row['name'],'role':'MANUAL_ONLY','org_family':row.get('family','UNKNOWN'),'rx_named':False,'dnc_named':True}
        evidence={field:{'status':'NO_FACTORY_PROFILE','source':'factory_corpus'} for field in FACTORY_FIELDS}
        card={'profile_id':_profile_id(identity),'origin':'OFFICIAL_MANUAL_ONLY','identity':identity,'support':{'notes':0,'styles':0,'segments':0,'grade':'NO_FACTORY_SUPPORT'},'factory_profile':None,'stability':'NO_FACTORY_SUPPORT','factory_evidence':evidence,'official_manual':{'exact_dnc':row,'family_semantics':family_semantics.get(row.get('family','UNKNOWN'),{})},'community':{'candidates':[],'authority':False},'unresolved':sorted(set(FACTORY_FIELDS+ALWAYS_UNKNOWN+('exact_trigger_context_on_hardware','audible_articulation_result'))),'authority':{'factory_numeric':False,'manual_mutation':False,'community_mutation':False,'hardware_confirmed':False},'completion_state':'COMPLETE_WITH_EXPLICIT_UNKNOWNS'}
        cards.append(card);manual_only.append(card)
    cards.sort(key=lambda row:(row['identity'].get('msb',999),row['identity'].get('lsb',999),row['identity'].get('program',999),_norm(row['identity'].get('sound')),row['identity'].get('role','')))
    summary={'factory_profiles':len(factory.get('profiles',[])),'manual_dnc_profiles':len(dnc.get('sounds',[])),'exact_dnc_factory_matches':len(matched),'manual_only_profiles':len(manual_only),'cards_total':len(cards),'complete_cards':sum(row['completion_state']=='COMPLETE_WITH_EXPLICIT_UNKNOWNS' for row in cards),'community_authority_cards':sum(bool(row['community']['authority']) for row in cards),'field_states':{field:{state:field_counts.get((field,state),0) for state in ('OBSERVED','OBSERVED_EMPTY','UNKNOWN_NOT_OBSERVED')} for field in FACTORY_FIELDS}}
    return {'schema':'PA800_PROFILE_COMPLETENESS_V1','meaning_of_complete':'All required fields exist; unsupported facts are explicit UNKNOWN and are not synthesized.','sources':{'official':len(sources.get('official_sources',[])),'community':len(sources.get('community_sources',[]))},'summary':summary,'cards':cards}


def render(report):
    summary=report['summary'];lines=['# Pa800 Profile Completeness Audit','',f"Factory profiles: **{summary['factory_profiles']}**",f"Manual DNC profiles: **{summary['manual_dnc_profiles']}**",f"Manual-only DNC cards: **{summary['manual_only_profiles']}**",f"Complete cards: **{summary['complete_cards']}/{summary['cards_total']}**",f"Community-authorized cards: **{summary['community_authority_cards']}**",'','`COMPLETE_WITH_EXPLICIT_UNKNOWNS` znači potpunu shemu i pošteno označene granice, ne izmišljene numeričke vrijednosti.','', '| Field | Observed | Empty | Unknown |','|---|---:|---:|---:|']
    for field,states in summary['field_states'].items():lines.append(f"| {field} | {states['OBSERVED']} | {states['OBSERVED_EMPTY']} | {states['UNKNOWN_NOT_OBSERVED']} |")
    return '\n'.join(lines)+'\n'


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--output',default=str(DATA/'factory_profile_completeness_v1.json'));parser.add_argument('--report',default=str(ROOT/'PROFILE_COMPLETENESS_AUDIT.md'));parser.add_argument('--csv',default=str(ROOT/'PROFILE_COMPLETENESS_CATALOG.csv'));args=parser.parse_args(argv);report=build();Path(args.output).write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');Path(args.report).write_text(render(report),encoding='utf-8')
    fields=('profile_id','origin','msb','lsb','program','sound','family','role','support_grade','styles','notes','stability','observed_fields','explicit_unknowns','exact_manual_dnc','community_candidates','completion_state')
    with Path(args.csv).open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for card in report['cards']:
            identity=card['identity'];support=card['support'];writer.writerow({'profile_id':card['profile_id'],'origin':card['origin'],'msb':identity.get('msb'),'lsb':identity.get('lsb'),'program':identity.get('program'),'sound':identity.get('sound'),'family':identity.get('org_family'),'role':identity.get('role'),'support_grade':support.get('grade'),'styles':support.get('styles'),'notes':support.get('notes'),'stability':card.get('stability'),'observed_fields':sum(row['status']=='OBSERVED' for row in card['factory_evidence'].values()),'explicit_unknowns':len(card['unresolved']),'exact_manual_dnc':bool(card['official_manual'].get('exact_dnc')),'community_candidates':'|'.join(card['community'].get('candidates',[])),'completion_state':card['completion_state']})
    print(json.dumps(report['summary'],indent=2,ensure_ascii=False));return 0 if report['summary']['factory_profiles']==542 and report['summary']['manual_dnc_profiles']==23 and report['summary']['complete_cards']==report['summary']['cards_total'] and report['summary']['community_authority_cards']==0 else 1


if __name__=='__main__':raise SystemExit(main())