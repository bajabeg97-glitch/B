"""Hierarchical, analyzer-only instrument intent model.

V3 connects observed identity, track role, phrase/note purpose, section and
ensemble relationships.  It deliberately grants no mutation authority: later
automation releases may consume only calibrated, ground-truth validated rows.
"""
from __future__ import annotations

from collections import Counter,defaultdict
import hashlib
import json


ROLE_ALTERNATIVES={
    'FOUNDATION_DRUM':['FOUNDATION_PERC','RIFF_OSTINATO'],
    'FOUNDATION_PERC':['FOUNDATION_DRUM','RIFF_OSTINATO'],
    'FOUNDATION_BASS':['RIFF_OSTINATO','COUNTER_LINE'],
    'HARMONIC_COMP':['PAD_BACKGROUND','RIFF_OSTINATO'],
    'PAD_BACKGROUND':['HARMONIC_COMP','COUNTER_LINE'],
    'RIFF_OSTINATO':['HARMONIC_COMP','LEAD'],
    'LEAD':['COUNTER_LINE','RIFF_OSTINATO'],
    'COUNTER_LINE':['LEAD','HARMONIC_COMP'],
    'ORNAMENT_FX':['UNKNOWN'],
    'UNKNOWN':[],
}

SENSITIVE_TYPES={'pitchwheel','aftertouch','polytouch'}
SENSITIVE_CCS={1,2,64,80,81}


def _intent_id(level,track,channel,start,end,label,ordinal=0):
    raw=f'{level}|{track}|{channel}|{start}|{end}|{label}|{ordinal}'
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:24]


def _controller_dependencies(mid):
    dependencies=defaultdict(set)
    for track_index,track in enumerate(mid.tracks):
        for msg in track:
            channel=getattr(msg,'channel',None)
            if channel is None:continue
            key=(track_index,int(channel))
            if msg.type=='control_change' and int(msg.control) in SENSITIVE_CCS:dependencies[key].add('CC%d'%int(msg.control))
            elif msg.type in SENSITIVE_TYPES:dependencies[key].add(msg.type.upper())
    return dependencies


def _identity_dependencies(ctx,controller_dependencies):
    out=[]
    if not ctx:return ['MISSING_CONTEXT']
    if ctx.identity.conflict:out.append('IDENTITY_CONFLICT')
    if ctx.identity.rx_named:out.append('RX_IDENTITY')
    if ctx.identity.dnc_named:out.append('DNC_IDENTITY')
    if str(ctx.family or '').upper() in ('SFX','SYNTH_FX'):out.append('SFX_PRESERVE')
    out.extend(sorted(controller_dependencies))
    return out


def _allowed_actions(evidence,confidence,dependencies,label):
    actions=['ANALYZE','SUGGEST']
    if label=='UNKNOWN' or confidence<.70:actions=['ANALYZE','REQUEST_GROUND_TRUTH']
    elif evidence=='E2' and confidence>=.90 and not dependencies:actions.append('BOUNDED_SHAPING_CANDIDATE_AFTER_CALIBRATION')
    return actions


def _section_for_tick(sections,tick):
    for section in sections:
        if int(section.get('start_tick',0))<=tick<int(section.get('end_tick',tick+1)):return section
    return None


def _phrase_label(role,intents):
    counts=Counter(intents);dominant=counts.most_common(1)[0][0] if counts else 'UNKNOWN'
    if role=='FOUNDATION_BASS':return 'BASS_'+dominant
    if role in ('FOUNDATION_DRUM','FOUNDATION_PERC'):return 'RHYTHMIC_'+dominant
    if role in ('LEAD','COUNTER_LINE'):return 'FOREGROUND_PHRASE'
    if role in ('HARMONIC_COMP','PAD_BACKGROUND'):return 'HARMONIC_TEXTURE'
    if role=='RIFF_OSTINATO':return 'REPEATED_CELL'
    return dominant if dominant!='NORMAL' else 'UNKNOWN'


def intent_digest(report):
    """Return a stable semantic digest excluding the digest field itself."""
    payload={key:value for key,value in report.items() if key!='intent_digest'}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')).hexdigest()


def analyze_instrument_intent(mid,notes,contexts,musical_context,understanding,family_intent=None,section_narrative=None):
    """Build track/phrase/note/section/ensemble intent without MIDI mutation."""
    functions={(int(row['track']),int(row['channel'])-1):row for row in musical_context.get('track_functions',[])}
    narratives={(int(row['track']),int(row['channel'])-1):row for row in understanding.get('track_narratives',[])}
    section_narrative=section_narrative or {};sections=section_narrative.get('sections') or musical_context.get('sections',[]);controllers=_controller_dependencies(mid);by_key=defaultdict(list)
    family_intent=family_intent or {};family_rows={(int(row['track']),int(row['channel'])-1,int(row['onset']),int(row['note']),int(row.get('occurrence',0))):row for row in family_intent.get('note_intents',[])}
    for note in notes:by_key[(note.track_index,note.channel)].append(note)
    tracks=[];phrases=[];note_rows=[];unknowns=[]
    for key in sorted(contexts):
        ctx=contexts[key];function=functions.get(key,{});label=function.get('function','UNKNOWN');confidence=float(function.get('confidence',0));evidence=function.get('evidence_level','E0');dependencies=_identity_dependencies(ctx,controllers.get(key,set()))
        if int((function.get('features') or {}).get('notes',0))<4 and evidence!='E2':label='UNKNOWN';confidence=min(confidence,.45);evidence='E0'
        track_id=_intent_id('track',key[0],key[1],0,max((n.off for n in by_key.get(key,[])),default=0),label)
        alternatives=[{'label':item,'confidence_upper_bound':round(max(0.0,1-confidence),3)} for item in ROLE_ALTERNATIVES.get(label,['UNKNOWN'])]
        unknown_reasons=[]
        if label=='UNKNOWN':unknown_reasons.append('INSUFFICIENT_ROLE_EVIDENCE')
        if confidence<.70:unknown_reasons.append('ROLE_CONFIDENCE_BELOW_AUTOMATION_FLOOR')
        if dependencies:unknown_reasons.append('PROTECTED_DEPENDENCIES_REQUIRE_SPECIALIZED_MODEL')
        tracks.append({'intent_id':track_id,'track':key[0],'channel':key[1]+1,'identity':{'address':list(ctx.identity.address()),'sound':ctx.identity.name,'family':ctx.family,'serialized_role':ctx.role},'label':label,'confidence':round(confidence,3),'evidence_level':evidence,'support':function.get('features',{}),'alternatives':alternatives,'unknown_reasons':unknown_reasons,'protected_dependencies':dependencies,'allowed_actions':_allowed_actions(evidence,confidence,dependencies,label),'automation_authority':False})
        if unknown_reasons:unknowns.append({'intent_id':track_id,'level':'track','track':key[0],'channel':key[1]+1,'reasons':unknown_reasons})
        narrative=narratives.get(key,{});phrase_defs=narrative.get('phrases',[])
        for ordinal,phrase in enumerate(phrase_defs):
            start=int(phrase.get('start_tick',0));end=int(phrase.get('end_tick',start));arr=[n for n in by_key.get(key,[]) if start<=n.onset<=end];phrase_label=_phrase_label(label,[n.intent for n in arr]);phrase_conf=min(confidence,float(phrase.get('confidence',.35)))
            phrase_id=_intent_id('phrase',key[0],key[1],start,end,phrase_label,ordinal);section=_section_for_tick(sections,start)
            phrase_unknown=[] if phrase_label!='UNKNOWN' and phrase_conf>=.60 else ['AMBIGUOUS_PHRASE_PURPOSE']
            phrases.append({'intent_id':phrase_id,'parent_intent_id':track_id,'track':key[0],'channel':key[1]+1,'start_tick':start,'end_tick':end,'label':phrase_label,'confidence':round(phrase_conf,3),'evidence_level':'E1' if phrase_label!='UNKNOWN' else 'E0','support':{'notes':len(arr),'dynamic_contour':phrase.get('dynamic_contour'),'section':section.get('label') if section else 'UNKNOWN'},'alternatives':[],'unknown_reasons':phrase_unknown,'protected_dependencies':dependencies,'allowed_actions':['ANALYZE','SUGGEST'] if not phrase_unknown else ['ANALYZE','REQUEST_GROUND_TRUTH'],'automation_authority':False})
        for ordinal,note in enumerate(sorted(by_key.get(key,[]),key=lambda row:(row.onset,row.note,row.occurrence))):
            section=_section_for_tick(sections,note.onset);specialized=family_rows.get((key[0],key[1],note.onset,note.note,note.occurrence));note_label=str(note.intent or 'UNKNOWN');note_confidence=min(confidence,.78 if note_label not in ('NORMAL','UNKNOWN') else .55);note_unknown=[]
            note_dependencies=list(dependencies)
            if specialized:
                note_label=specialized['label'];note_confidence=min(confidence,float(specialized['confidence']));note_dependencies=sorted(set(note_dependencies+specialized.get('protected_dependencies',[])))
            elif note_label in ('NORMAL','UNKNOWN'):note_unknown.append('NO_SPECIALIZED_FAMILY_INTENT')
            note_id=_intent_id('note',key[0],key[1],note.onset,note.off,note_label,ordinal)
            note_rows.append({'intent_id':note_id,'parent_intent_id':track_id,'track':key[0],'channel':key[1]+1,'note':note.note,'velocity':note.velocity,'onset':note.onset,'off':note.off,'occurrence':note.occurrence,'label':note_label,'confidence':round(note_confidence,3),'evidence_level':specialized.get('evidence_level','E1') if specialized else ('E1' if not note_unknown else 'E0'),'support':{'track_role':label,'section':section.get('label') if section else 'UNKNOWN','metric_position_ticks':note.onset%max(1,mid.ticks_per_beat*4),'family_intent':specialized},'alternatives':[],'unknown_reasons':note_unknown,'protected_dependencies':note_dependencies,'allowed_actions':['ANALYZE','PRESERVE'] if note_dependencies else (['ANALYZE','SUGGEST'] if not note_unknown else ['ANALYZE']),'automation_authority':False})
    section_rows=[]
    for ordinal,section in enumerate(sections):
        label=section.get('label','UNKNOWN');confidence=float(section.get('confidence',0));start=int(section.get('start_tick',0));end=int(section.get('end_tick',start));evidence=section.get('evidence_level','E0')
        section_rows.append({'intent_id':_intent_id('section',-1,-1,start,end,label,ordinal),'label':label,'start_tick':start,'end_tick':end,'confidence':round(confidence,3),'evidence_level':evidence,'support':{'notes':section.get('notes'),'active_tracks':section.get('active_tracks'),'density_notes_per_beat':section.get('density_notes_per_beat')},'alternatives':[],'unknown_reasons':[] if evidence=='E2' or confidence>=.70 else ['SECTION_REQUIRES_GROUND_TRUTH'],'protected_dependencies':[],'allowed_actions':['ANALYZE','SUGGEST'],'automation_authority':False})
    ensemble=[]
    for domain,rows in (('groove',understanding.get('groove',{}).get('relationships',[])),('interaction',understanding.get('interaction',{}).get('relationships',[]))):
        for ordinal,row in enumerate(rows):
            label=row.get('relationship','UNKNOWN');confidence=float(row.get('confidence',0));ensemble.append({'intent_id':_intent_id('ensemble',-1,-1,ordinal,ordinal,label,ordinal),'domain':domain,'label':label,'confidence':round(confidence,3),'evidence_level':row.get('evidence_level','E1'),'support':row,'alternatives':[],'unknown_reasons':[] if confidence>=.60 else ['WEAK_ENSEMBLE_RELATION'],'protected_dependencies':['CROSS_TRACK_FINGERPRINT'],'allowed_actions':['ANALYZE','PRESERVE_RELATIONSHIP'],'automation_authority':False})
    report={'schema':'PA800_INSTRUMENT_INTENT_V3','analyzer_only':True,'mutations':0,'authority_granted':False,'content_type':musical_context.get('content_type'),'section_model':{'schema':section_narrative.get('schema'),'digest':section_narrative.get('digest'),'sections':section_narrative.get('summary',{}).get('sections',len(sections)),'authority_granted':False},'family_models':{'schema':family_intent.get('schema'),'digest':family_intent.get('digest'),'classified_notes':family_intent.get('summary',{}).get('classified_notes',0),'authority_granted':False},'track_intents':tracks,'phrase_intents':phrases,'note_intents':note_rows,'section_intents':section_rows,'ensemble_intents':ensemble,'unknowns':unknowns,'automation':{'policy':'NO_NEW_AUTHORITY_IN_2.5.3','candidate_rows':sum('BOUNDED_SHAPING_CANDIDATE_AFTER_CALIBRATION' in row['allowed_actions'] for row in tracks),'applied_actions':0,'blocked_rows':sum(bool(row['unknown_reasons'] or row['protected_dependencies']) for row in tracks)},'summary':{'tracks':len(tracks),'phrases':len(phrases),'notes':len(note_rows),'sections':len(section_rows),'ensemble_relations':len(ensemble),'specialized_family_notes':sum(row.get('support',{}).get('family_intent') is not None for row in note_rows),'unknown_tracks':sum(row['label']=='UNKNOWN' for row in tracks),'event_attribution_percent':100.0 if len(note_rows)==len(notes) else round(100*len(note_rows)/max(1,len(notes)),3)}}
    report['intent_digest']=intent_digest(report)
    return report


def render_intent_summary(report):
    lines=['Instrument Intent V3','-'*72]
    for row in report.get('track_intents',[]):lines.append(f"Track {row['track']} ch {row['channel']}: {row['label']} ({row['confidence']:.2f}, {row['evidence_level']})")
    summary=report.get('summary',{});lines.append(f"Notes attributed: {summary.get('notes',0)}; authority: analyzer-only")
    return '\n'.join(lines)+'\n'