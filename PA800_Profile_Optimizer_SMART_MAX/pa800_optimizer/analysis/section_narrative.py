"""Analyzer-only Section & Narrative V3.

The model treats serialized Style Element/CV labels and explicit Song markers
as evidence, while inferred Song boundaries require several independent
musical changes.  Velocity alone never creates a section boundary.
"""
from __future__ import annotations

from collections import Counter,defaultdict
import hashlib
import json
import math
import re

from .meter_map import _build_bar_spans,_meter_changes


SECTION_WORDS={
    'INTRO':'INTRO','VERSE':'VERSE','PRECHORUS':'PRE_CHORUS','PRE CHORUS':'PRE_CHORUS',
    'CHORUS':'CHORUS','REFRAIN':'CHORUS','BRIDGE':'BRIDGE','MIDDLE 8':'BRIDGE',
    'BREAK':'BREAK','SOLO':'SOLO','OUTRO':'ENDING','ENDING':'ENDING','CODA':'ENDING',
}


def _median(values,default=0.0):
    values=sorted(values)
    if not values:return default
    middle=len(values)//2
    return float(values[middle]) if len(values)%2 else (values[middle-1]+values[middle])/2


def _jaccard(a,b):
    union=set(a)|set(b)
    return 1.0 if not union else len(set(a)&set(b))/len(union)


def _marker_label(text):
    clean=re.sub(r'[^A-Z0-9 ]+',' ',str(text).upper()).strip()
    for token,label in SECTION_WORDS.items():
        if token in clean:return label
    return None


def _markers(mid):
    rows=[]
    for track_index,track in enumerate(mid.tracks):
        tick=0
        for msg in track:
            tick+=int(getattr(msg,'time',0))
            if msg.type not in ('marker','text','cue_marker'):continue
            text=str(getattr(msg,'text','')).strip();label=_marker_label(text)
            if label:rows.append({'tick':tick,'track':track_index,'text':text,'label':label,'evidence_level':'E2'})
    return sorted(rows,key=lambda row:(row['tick'],row['track'],row['label']))


def _meter(mid):
    for track in mid.tracks:
        for msg in track:
            if msg.type=='time_signature':return int(msg.numerator),int(msg.denominator)
    return 4,4


def _bar_features(notes,contexts,tpb,bar_spans):
    bars=[]
    for span in bar_spans:
        index=span['index'];start=span['start_tick'];end=span['end_tick'];bar_ticks=span['bar_ticks'];arr=[note for note in notes if start<=note.onset<max(start+1,end)];sounding=[note for note in notes if note.onset<max(start+1,end) and note.off>start];active={(note.track_index,note.channel) for note in sounding};roles=Counter();families=Counter();rhythm=[];beat_harmony=defaultdict(set)
        for note in sounding:
            ctx=contexts.get((note.track_index,note.channel));role=str((ctx.role if ctx else 'UNKNOWN') or 'UNKNOWN').upper();family=str((ctx.family if ctx else 'UNKNOWN') or 'UNKNOWN').upper();roles[role]+=1;families[family]+=1
        for note in arr:
            subdivision=min(15,int(16*(note.onset-start)/max(1,bar_ticks)));rhythm.append((note.track_index,note.channel,subdivision))
            beat_harmony[(note.onset-start)//max(1,tpb)].add(note.note%12)
        harmonic_states=[tuple(sorted(value)) for _beat,value in sorted(beat_harmony.items())];harmonic_changes=sum(a!=b for a,b in zip(harmonic_states,harmonic_states[1:]));duration=max(1,end-start)
        bars.append({'index':index,'start_tick':start,'end_tick':end,'duration_ticks':duration,'bar_ticks':bar_ticks,'partial':span['partial'],'numerator':span['numerator'],'denominator':span['denominator'],'notes':len(arr),'sounding_notes':len(sounding),'density_notes_per_beat':round(len(arr)/(duration/max(1,tpb)),4),'velocity_median':round(_median([note.velocity for note in arr]),3),'active_contexts':sorted([list(key) for key in active]),'roles':dict(sorted(roles.items())),'families':dict(sorted(families.items())),'rhythm_signature':sorted(set(rhythm)),'pitch_classes':sorted({note.note%12 for note in arr}),'harmonic_changes':harmonic_changes})
    return bars


def _change(a,b):
    active_a={tuple(value) for value in a['active_contexts']};active_b={tuple(value) for value in b['active_contexts']};layer_change=1-_jaccard(active_a,active_b);rhythm_change=1-_jaccard(a['rhythm_signature'],b['rhythm_signature']);harmony_change=1-_jaccard(a['pitch_classes'],b['pitch_classes']);density_change=abs(b['density_notes_per_beat']-a['density_notes_per_beat'])/max(.5,a['density_notes_per_beat'],b['density_notes_per_beat']);harmonic_rhythm_change=min(1,abs(b['harmonic_changes']-a['harmonic_changes'])/2);velocity_change=abs(b['velocity_median']-a['velocity_median'])/127
    score=.38*layer_change+.30*rhythm_change+.17*harmony_change+.10*min(1,density_change)+.05*harmonic_rhythm_change
    changed=sum(value>=.30 for value in (layer_change,rhythm_change,harmony_change,density_change,harmonic_rhythm_change))
    velocity_only=velocity_change>=.12 and score<.30 and layer_change<.10 and rhythm_change<.10 and density_change<.10
    return {'score':round(score,4),'layer_change':round(layer_change,4),'rhythm_change':round(rhythm_change,4),'harmony_change':round(harmony_change,4),'density_change':round(min(1,density_change),4),'harmonic_rhythm_change':round(harmonic_rhythm_change,4),'velocity_change':round(velocity_change,4),'independent_signals':changed,'velocity_only':velocity_only}


def _signature(bars):
    rhythm=Counter();roles=Counter();families=Counter()
    for bar in bars:
        rhythm.update(tuple(value) for value in bar['rhythm_signature']);roles.update(bar['roles']);families.update(bar['families'])
    return {'rhythm':sorted(rhythm),'roles':sorted(roles),'families':sorted(families),'mean_density':round(sum(bar['density_notes_per_beat'] for bar in bars)/max(1,len(bars)),3),'mean_layers':round(sum(len(bar['active_contexts']) for bar in bars)/max(1,len(bars)),3)}


def _similar(a,b):
    return .50*_jaccard(a['rhythm'],b['rhythm'])+.30*_jaccard(a['roles'],b['roles'])+.20*_jaccard(a['families'],b['families'])


def _song_sections(mid,notes,contexts,bar_spans,markers):
    bars=_bar_features(notes,contexts,mid.ticks_per_beat,bar_spans);marker_by_bar=defaultdict(list)
    for marker in markers:
        target=next((bar['index'] for bar in bars if bar['start_tick']<=marker['tick']<bar['end_tick']),len(bars)-1)
        marker_by_bar[max(0,target)].append(marker)
    boundaries={0,len(bars)};boundary_evidence=[]
    for index in range(1,len(bars)):
        change=_change(bars[index-1],bars[index]);marked=marker_by_bar.get(index,[])
        inferred=change['score']>=.38 and change['independent_signals']>=2 and not change['velocity_only'] and not (bars[index]['partial'] and bars[index]['notes']==0)
        if marked or inferred:boundaries.add(index)
        boundary_evidence.append({'bar':index+1,'tick':bars[index]['start_tick'],'explicit_markers':marked,'change':change,'accepted':bool(marked or inferred),'reason':'EXPLICIT_MARKER' if marked else 'MULTI_SIGNAL_CHANGE' if inferred else 'VELOCITY_ONLY_REJECTED' if change['velocity_only'] else 'BELOW_BOUNDARY_GATE'})
    ordered=sorted(boundaries);segments=[]
    for ordinal,(left,right) in enumerate(zip(ordered,ordered[1:])):
        chunk=bars[left:right];segment_markers=[row for bar in range(left,right) for row in marker_by_bar.get(bar,[])];signature=_signature(chunk);label=segment_markers[0]['label'] if segment_markers else 'UNKNOWN';evidence='E2' if segment_markers else 'E1';confidence=.99 if segment_markers else .45
        segments.append({'index':ordinal,'start_tick':chunk[0]['start_tick'],'end_tick':chunk[-1]['end_tick'],'start_bar':left+1,'end_bar':right,'bars':right-left,'label':label,'confidence':confidence,'evidence_level':evidence,'markers':segment_markers,'signature':signature,'notes':sum(bar['notes'] for bar in chunk),'density_notes_per_beat':signature['mean_density'],'active_tracks_proxy':signature['mean_layers'],'velocity_median_proxy':round(_median([bar['velocity_median'] for bar in chunk]),3),'harmonic_changes':sum(bar['harmonic_changes'] for bar in chunk)})
    signatures=[row['signature'] for row in segments];repetitions=[]
    for index,row in enumerate(segments):
        peers=[other for other in range(len(segments)) if other!=index and _similar(signatures[index],signatures[other])>=.82];repetitions.append(peers)
    densities=[row['density_notes_per_beat'] for row in segments];median_density=_median(densities)
    for index,row in enumerate(segments):
        if row['label']!='UNKNOWN':continue
        peers=repetitions[index];middle=0<index<len(segments)-1
        if row['notes']==0 or row['density_notes_per_beat']<=max(.15,median_density*.30):label,confidence='BREAK_CANDIDATE',.72
        elif index==0 and (row['bars']==1 or row['density_notes_per_beat']<median_density*.70):label,confidence='INTRO_CANDIDATE',.64
        elif index==len(segments)-1 and row['density_notes_per_beat']<median_density*.70:label,confidence='ENDING_CANDIDATE',.62
        elif peers and row['density_notes_per_beat']>=median_density*1.12:label,confidence='CHORUS_CANDIDATE',.66
        elif peers:label,confidence='VERSE_OR_RETURN_CANDIDATE',.62
        elif middle and len(segments)>=3:label,confidence='BRIDGE_OR_CONTRAST_CANDIDATE',.55
        else:label,confidence='UNKNOWN',.40
        row.update({'label':label,'confidence':confidence})
    return bars,segments,boundary_evidence,repetitions


def _style_sections(musical_context):
    rows=[]
    for index,section in enumerate(musical_context.get('sections',[])):
        rows.append({'index':index,'start_tick':int(section.get('start_tick',0)),'end_tick':int(section.get('end_tick',0)),'start_bar':None,'end_bar':None,'bars':None,'label':section.get('label','STYLE_WHOLE_UNLABELED'),'cv':section.get('cv'),'confidence':float(section.get('confidence',.35)),'evidence_level':section.get('evidence_level','E0'),'markers':[],'signature':{},'notes':section.get('notes',0),'density_notes_per_beat':section.get('density_notes_per_beat'),'active_tracks_proxy':section.get('active_tracks',0),'velocity_median_proxy':section.get('velocity_median_proxy'),'harmonic_changes':None})
    return rows


def _narrative(sections):
    rows=[];focus=[]
    for index,section in enumerate(sections):
        previous=sections[index-1] if index else None
        if previous is None:relationship='START'
        else:
            density_ratio=(section.get('density_notes_per_beat') or 0)-(previous.get('density_notes_per_beat') or 0);layer_delta=(section.get('active_tracks_proxy') or 0)-(previous.get('active_tracks_proxy') or 0);velocity_delta=(section.get('velocity_median_proxy') or 0)-(previous.get('velocity_median_proxy') or 0);similarity=_similar(previous.get('signature',{}),section.get('signature',{})) if previous.get('signature') and section.get('signature') else 0
            if similarity>=.82 and abs(layer_delta)<.5 and abs(density_ratio)<.25 and abs(velocity_delta)>=12:relationship='DYNAMIC_CHANGE_SAME_PATTERN'
            elif layer_delta>=.45 or density_ratio>=.50:relationship='BUILD'
            elif layer_delta<=-.45 or density_ratio<=-.50:relationship='RELEASE'
            elif similarity>=.82:relationship='RETURN_OR_CONTINUATION'
            else:relationship='CONTRAST'
        rows.append({'from_section':None if index==0 else index-1,'to_section':index,'relationship':relationship,'evidence_level':'E2' if section.get('evidence_level')=='E2' else 'E1','automation_authority':False})
        focus.append({'section_index':index,'label':section.get('label'),'status':'SECTION_FOCUS_REQUIRES_ENSEMBLE_GRAPH','automation_authority':False})
    return rows,focus


def section_narrative_digest(report):
    payload={key:value for key,value in report.items() if key!='digest'}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def analyze_section_narrative(mid,notes,contexts,musical_context,understanding=None):
    changes=_meter_changes(mid);numerator,denominator=changes[0]['numerator'],changes[0]['denominator'];bar_ticks=max(1,int(round(mid.ticks_per_beat*numerator*4/denominator)));end_tick=max((note.off for note in notes),default=bar_ticks);bar_spans=_build_bar_spans(mid,end_tick);markers=_markers(mid);content_type=str(musical_context.get('content_type') or 'song').lower()
    if content_type=='style':bars=[];sections=_style_sections(musical_context);boundaries=[];repetitions=[[] for _ in sections];method='SERIALIZED_STYLE_ELEMENT_CV'
    else:bars,sections,boundaries,repetitions=_song_sections(mid,notes,contexts,bar_spans,markers);method='MARKERS_PLUS_MULTI_SIGNAL_CHANGE_NO_VELOCITY_BOUNDARY'
    transitions,focus=_narrative(sections);overlaps=[]
    for section in sections[1:]:
        tick=int(section['start_tick']);spanning=[{'track':note.track_index,'channel':note.channel+1,'note':note.note,'onset':note.onset,'off':note.off} for note in notes if note.onset<tick<note.off]
        if spanning:overlaps.append({'boundary_tick':tick,'notes':spanning,'policy':'PRESERVE_OVERLAP_DO_NOT_HARD_SPLIT'})
    unknown=[{'section_index':row['index'],'reason':'INFERRED_LABEL_REQUIRES_GROUND_TRUTH'} for row in sections if row.get('evidence_level')!='E2']
    report={'schema':'PA800_SECTION_NARRATIVE_V3','analyzer_only':True,'mutations':0,'authority_granted':False,'content_type':content_type,'meter':{'numerator':numerator,'denominator':denominator,'bar_ticks':bar_ticks,'ticks_per_beat':mid.ticks_per_beat,'changes':changes},'method':method,'markers':markers,'bars':bars,'sections':sections,'boundary_evidence':boundaries,'repetition_links':repetitions,'transitions':transitions,'focus_handoffs':focus,'boundary_overlaps':overlaps,'unknowns':unknown,'automation':{'policy':'NO_SECTION_AUTO_AUTHORITY_BEFORE_GROUND_TRUTH','applied_actions':0},'summary':{'sections':len(sections),'explicit_sections':sum(row.get('evidence_level')=='E2' for row in sections),'inferred_sections':sum(row.get('evidence_level')!='E2' for row in sections),'accepted_boundaries':sum(row.get('accepted') for row in boundaries),'rejected_velocity_only':sum(row.get('reason')=='VELOCITY_ONLY_REJECTED' for row in boundaries),'overlap_boundaries':len(overlaps)}}
    report['digest']=section_narrative_digest(report);return report


def render_section_narrative_summary(report):
    lines=['Section & Narrative V3','-'*72]
    for row in report.get('sections',[]):lines.append(f"Section {row['index']}: {row['label']} ({row['start_tick']}-{row['end_tick']}, {row['evidence_level']})")
    lines.append('Authority: analyzer-only');return '\n'.join(lines)+'\n'