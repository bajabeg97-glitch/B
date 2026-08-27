"""Exact per-instrument neural routing profiles derived without invented evidence."""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path

SCHEMA='PA800_EXACT_INSTRUMENT_NEURAL_PROFILES_V1'
PERMANENT_PRESERVE={'SFX','SYNTH_FX'}
FAMILY_POLICIES={
 'PIANO':('CHORD_OR_LINE',('ONSET_SPIKE','GATE_TRUNCATE','GATE_OVERLAP'),('CC64','CHORD_BALANCE')),
 'BASS':('DRUM_LOCKED_LINE',('ONSET_SPIKE','GATE_TRUNCATE','GROOVE_DRIFT'),('DRUM_ANCHOR','SPECIAL_PITCH')),
 'GUITAR':('STRUM_OR_LINE',('ONSET_SPIKE','GATE_TRUNCATE','CHORD_DESYNC','GROOVE_DRIFT'),('STRUM_DIRECTION','SPECIAL_PITCH','RX_DNC')),
 'DRUM_KIT':('KIT_KEY_EVENT',('ONSET_SPIKE','DUPLICATE_HIT','GROOVE_DRIFT'),('GHOST_NOTE','KIT_KEY_IDENTITY')),
 'PERCUSSIVE':('TRANSIENT_EVENT',('ONSET_SPIKE','DUPLICATE_HIT','GROOVE_DRIFT'),('SPECIAL_PITCH',)),
 'CHROMATIC_PERC':('TRANSIENT_PITCHED',('ONSET_SPIKE','GATE_TRUNCATE'),('TRANSIENT_TAIL',)),
 'ORGAN':('LEGATO_OR_STAB',('ONSET_SPIKE','GATE_TRUNCATE','GATE_OVERLAP'),('LEGATO','CONTROLLER_STATE','VELOCITY_INSENSITIVE')),
 'STRINGS':('PHRASE_OR_CHORD',('ONSET_SPIKE','GATE_TRUNCATE','GATE_OVERLAP','CHORD_DESYNC'),('SUSTAIN_TAIL','VOICE_LEADING')),
 'ENSEMBLE':('PHRASE_OR_CHORD',('ONSET_SPIKE','GATE_TRUNCATE','GATE_OVERLAP','CHORD_DESYNC'),('SUSTAIN_TAIL','VOICE_LEADING')),
 'SYNTH_PAD':('SUSTAIN_LAYER',('GATE_TRUNCATE','GATE_OVERLAP','CHORD_DESYNC'),('SUSTAIN_TAIL','CONTROLLER_STATE')),
 'BRASS':('BREATH_PHRASE_OR_STAB',('ONSET_SPIKE','GATE_TRUNCATE'),('CC1','PITCH_BEND','AFTERTOUCH','NOTE_OFF_NOISE')),
 'REED':('BREATH_PHRASE',('ONSET_SPIKE','GATE_TRUNCATE'),('CC1','CC2','PITCH_BEND','LEGATO')),
 'PIPE':('BREATH_PHRASE',('ONSET_SPIKE','GATE_TRUNCATE'),('CC1','CC2','PITCH_BEND','LEGATO')),
 'ACCORDION_REED':('BELLOWS_OR_BREATH',('ONSET_SPIKE','GATE_TRUNCATE'),('CC1','CC2','PITCH_BEND','LEGATO')),
 'SYNTH_LEAD':('EXPRESSIVE_LINE',('ONSET_SPIKE','GATE_TRUNCATE'),('CC1','PITCH_BEND','AFTERTOUCH')),
 'ETHNIC':('EXACT_ONLY_LINE',('ONSET_SPIKE','GATE_TRUNCATE'),('SPECIAL_PITCH','CULTURAL_SEMANTICS')),
 'SFX':('PERMANENT_PRESERVE',(),('RAW_EVENT_IDENTITY',)),
 'SYNTH_FX':('PERMANENT_PRESERVE',(),('RAW_EVENT_IDENTITY',)),
}
VECTOR_FIELDS=('key_center','key_span','duration_center','gate_center','density_center','chord_size','interval_center','timing_center','support_notes','support_styles')


def _center(profile,name):
    row=(profile or {}).get(name) or {};return row.get('ideal_center')


def _span(profile,name):
    row=(profile or {}).get(name) or {};low=row.get('ideal_min');high=row.get('ideal_max');return None if low is None or high is None else high-low


def _timing_center(profile):
    rows=(profile or {}).get('timing_residual_ticks') or {};values=[row.get('ideal_center') for row in rows.values() if isinstance(row,dict) and row.get('ideal_center') is not None];return None if not values else sum(values)/len(values)


def _vector(card):
    profile=card.get('factory_profile') or {};support=card.get('support') or {};raw=[_center(profile,'key'),_span(profile,'key'),_center(profile,'duration_ticks'),_center(profile,'gate_to_next_onset'),_center(profile,'notes_per_bar'),_center(profile,'exact_onset_chord_size'),_center(profile,'signed_interval'),_timing_center(profile),support.get('notes'),support.get('styles')]
    scales=(127,127,4096,8,32,8,24,48,100000,252);return [None if value is None else round(max(-2,min(2,float(value)/scale)),6) for value,scale in zip(raw,scales)],dict(zip(VECTOR_FIELDS,raw))


def build_instrument_profile_catalog(completeness,positive_models=None,encoder_model=None):
    completeness=json.loads(Path(completeness).read_text(encoding='utf-8')) if isinstance(completeness,(str,Path)) else completeness;positive_models=json.loads(Path(positive_models).read_text(encoding='utf-8')) if isinstance(positive_models,(str,Path)) else (positive_models or {});encoder_model=json.loads(Path(encoder_model).read_text(encoding='utf-8')) if isinstance(encoder_model,(str,Path)) else (encoder_model or {})
    positive={(str(row.get('family')).upper(),tuple(row.get('address') or ())):row for row in positive_models.get('allowed',[])};profiles=[]
    for card in completeness.get('cards',[]):
        identity=card.get('identity') or {};family=str(identity.get('org_family') or 'UNKNOWN').upper();policy=FAMILY_POLICIES.get(family,('UNKNOWN_PRESERVE',(),('UNKNOWN_FAMILY',)));address=(identity.get('msb'),identity.get('lsb'),identity.get('program'));factory=card.get('factory_profile') or {};vector,raw_vector=_vector(card);manual=(card.get('official_manual') or {}).get('exact_dnc');family_manual=(card.get('official_manual') or {}).get('family_semantics') or {};special=bool(factory.get('special_pitch_candidates'));controllers=sorted(set(family_manual.get('controllers') or []),key=lambda value:(str(type(value)),str(value)));positive_row=positive.get((family,address));permanent=family in PERMANENT_PRESERVE;protected=permanent or bool(identity.get('rx_named')) or bool(identity.get('dnc_named')) or card.get('origin')=='OFFICIAL_MANUAL_ONLY'
        allowed=[] if protected else [name for name in policy[1] if name not in ('GATE_TRUNCATE','GATE_OVERLAP') or (card.get('factory_evidence') or {}).get('gate_to_next_onset',{}).get('status')=='OBSERVED']
        profile={'instrument_profile_id':'NIP-'+card['profile_id'],'source_profile_id':card['profile_id'],'scope':'EXACT_SOUND_ROLE','origin':card.get('origin'),'identity':identity,'family':family,'performance_unit':policy[0],'support':card.get('support'),'stability':card.get('stability'),'evidence_vector':vector,'evidence_vector_raw':raw_vector,'evidence_mask':[value is not None for value in vector],'factory_fields':{key:value.get('status') for key,value in (card.get('factory_evidence') or {}).items()},'controller_guards':controllers,'musical_guards':sorted(set(policy[2])|set(family_manual.get('guards') or [])),'special_pitch_protected':special,'manual_dnc_capabilities':(manual or {}).get('capabilities',[]),'eligible_defect_suggestions':allowed,'grouped_proxy_models':(positive_row or {}).get('models',[]),'grouped_proxy_evidence':None if not positive_row else {key:positive_row.get(key) for key in ('stability','median_loo_error','max_loo_error')},'encoder':{'model_digest':encoder_model.get('model_digest'),'dimensions':encoder_model.get('hidden_size'),'exact_embedding_status':'NO_EXACT_PER_INSTRUMENT_PERFORMANCE_PAIR','family_prior_only':True},'unresolved':card.get('unresolved',[]),'routing':'PRESERVE' if protected else ('EXACT_PROXY_SUGGEST' if positive_row else 'EXACT_EVIDENCE_ANALYZE'),'protected':protected,'production_auto':False,'mutations':0,'authority_granted':False}
        profiles.append(profile)
    families=Counter(row['family'] for row in profiles);payload={'schema':SCHEMA,'profiles':profiles,'summary':{'profiles':len(profiles),'factory_profiles':sum(row['origin']=='FACTORY_CORPUS' for row in profiles),'manual_only_profiles':sum(row['origin']=='OFFICIAL_MANUAL_ONLY' for row in profiles),'families':dict(sorted(families.items())),'family_count':len(families),'protected_profiles':sum(row['protected'] for row in profiles),'suggestion_profiles':sum(bool(row['eligible_defect_suggestions']) for row in profiles),'grouped_proxy_profiles':sum(bool(row['grouped_proxy_models']) for row in profiles),'exact_embeddings':sum(row['encoder']['exact_embedding_status']=='EXACT' for row in profiles),'production_auto_profiles':sum(row['production_auto'] for row in profiles)},'model_digest':encoder_model.get('model_digest'),'velocity_neural_input':False,'velocity_neural_output':False,'mutations':0,'authority_granted':False}
    payload['catalog_digest']=hashlib.sha256(json.dumps({key:value for key,value in payload.items() if key!='catalog_digest'},sort_keys=True,separators=(',',':')).encode()).hexdigest();return payload


def validate_instrument_profile_catalog(catalog):
    errors=[];profiles=catalog.get('profiles') or [];summary=catalog.get('summary') or {}
    if catalog.get('schema')!=SCHEMA:errors.append('schema')
    if len(profiles)!=565 or summary.get('profiles')!=565:errors.append('profile_count')
    if summary.get('factory_profiles')!=542 or summary.get('manual_only_profiles')!=23:errors.append('origin_counts')
    if len({row.get('instrument_profile_id') for row in profiles})!=len(profiles):errors.append('duplicate_profile_id')
    if set(summary.get('families') or {})!=set(FAMILY_POLICIES):errors.append('family_coverage')
    if catalog.get('velocity_neural_input') is not False or catalog.get('velocity_neural_output') is not False:errors.append('velocity_boundary')
    for row in profiles:
        if row.get('family') not in FAMILY_POLICIES:errors.append('unknown_family:'+str(row.get('instrument_profile_id')))
        if len(row.get('evidence_vector') or [])!=len(VECTOR_FIELDS):errors.append('vector_shape:'+str(row.get('instrument_profile_id')))
        if any('VELOCITY' in str(value).upper() for value in row.get('eligible_defect_suggestions',[])):errors.append('velocity_suggestion:'+str(row.get('instrument_profile_id')))
        if any(str(key).lower().startswith('velocity') for key in (row.get('evidence_vector_raw') or {})):errors.append('velocity_vector:'+str(row.get('instrument_profile_id')))
        if row.get('authority_granted') is not False or row.get('production_auto') is not False or row.get('mutations')!=0:errors.append('authority:'+str(row.get('instrument_profile_id')))
        if row.get('origin')=='OFFICIAL_MANUAL_ONLY' and row.get('routing')!='PRESERVE':errors.append('manual_only_not_preserved:'+str(row.get('instrument_profile_id')))
        if row.get('family') in PERMANENT_PRESERVE and (row.get('routing')!='PRESERVE' or row.get('eligible_defect_suggestions')):errors.append('permanent_preserve:'+str(row.get('instrument_profile_id')))
    digest=hashlib.sha256(json.dumps({key:value for key,value in catalog.items() if key!='catalog_digest'},sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if digest!=catalog.get('catalog_digest'):errors.append('catalog_digest')
    return {'schema':'PA800_EXACT_INSTRUMENT_NEURAL_PROFILES_AUDIT_V1','pass':not errors,'errors':errors,'profiles':len(profiles),'families':len(set(row.get('family') for row in profiles)),'authority_granted':False}


def resolve_instrument_profile(catalog,msb,lsb,program,sound=None,role=None):
    candidates=[row for row in catalog.get('profiles',[]) if (row['identity'].get('msb'),row['identity'].get('lsb'),row['identity'].get('program'))==(msb,lsb,program)]
    if sound is not None:candidates=[row for row in candidates if str(row['identity'].get('sound','')).casefold()==str(sound).casefold()]
    if role is not None:candidates=[row for row in candidates if row['identity'].get('role')==role]
    return {'status':'EXACT' if len(candidates)==1 else ('NOT_FOUND' if not candidates else 'AMBIGUOUS_PRESERVE'),'profile':candidates[0] if len(candidates)==1 else None,'candidate_ids':[row['instrument_profile_id'] for row in candidates],'authority_granted':False}
