"""Analyzer-only family intent models for Drum, Bass, Guitar and Piano/EP."""
from __future__ import annotations

from collections import Counter,defaultdict
import hashlib
import json


MODELED_FAMILIES={'DRUM_KIT','PERCUSSION','BASS','GUITAR','PIANO','ELECTRIC_PIANO'}


def _key(note):return (note.track_index,note.channel,note.onset,note.note,note.occurrence)


def _row(note,family,label,confidence,support,dependencies=None,evidence='E1'):
    dependencies=sorted(set(dependencies or []));raw=f'{note.track_index}|{note.channel}|{note.onset}|{note.note}|{note.occurrence}|{family}|{label}'
    return {'family_intent_id':hashlib.sha256(raw.encode()).hexdigest()[:24],'track':note.track_index,'channel':note.channel+1,'note':note.note,'onset':note.onset,'off':note.off,'occurrence':note.occurrence,'family':family,'label':label,'confidence':round(float(confidence),3),'evidence_level':evidence,'support':support,'protected_dependencies':dependencies,'allowed_actions':['ANALYZE','PRESERVE'] if dependencies else ['ANALYZE','SUGGEST'],'automation_authority':False,'mutations':0}


def _controller_states(mid):
    state={};result={}
    for track_index,track in enumerate(mid.tracks):
        tick=0
        for event_index,msg in enumerate(track):
            tick+=int(getattr(msg,'time',0));channel=getattr(msg,'channel',None)
            if channel is None:continue
            key=(track_index,int(channel));current=state.setdefault(key,{'cc64':0,'expressive':set()})
            if msg.type=='control_change':
                if msg.control==64:current['cc64']=msg.value
                if msg.control in (1,2,64,80,81):current['expressive'].add('CC%d'%msg.control)
            elif msg.type in ('pitchwheel','aftertouch','polytouch'):current['expressive'].add(msg.type.upper())
            if msg.type=='note_on' and msg.velocity>0:result[(track_index,int(channel),event_index)]={'damper_active':current['cc64']>=64,'expressive':sorted(current['expressive'])}
    return result


def _section_boundaries(musical_context,section_narrative=None):
    sections=(section_narrative or {}).get('sections') or musical_context.get('sections',[]);return sorted({int(value) for row in sections for value in (row.get('start_tick',0),row.get('end_tick',0)) if int(value)>0})


def _near_boundary(tick,boundaries,threshold):return bool(boundaries) and min(abs(tick-value) for value in boundaries)<=threshold


def _clusters(notes,window):
    clusters=[]
    for note in sorted(notes,key=lambda item:(item.onset,item.note,item.occurrence)):
        if not clusters or note.onset-clusters[-1][-1].onset>window:clusters.append([note])
        else:clusters[-1].append(note)
    return clusters


def _drum_rows(notes,tpb,boundaries,family):
    rows=[];beat_groups=defaultdict(list)
    for note in notes:beat_groups[note.onset//max(1,tpb)].append(note)
    for note in notes:
        beat=(note.onset//max(1,tpb))%4;deps=[]
        if note.velocity<=25:label,confidence='GHOST_HIT_CANDIDATE',.72
        elif note.note in (35,36):label,confidence='KICK_ANCHOR',.86
        elif note.note in (38,40) and beat in (1,3):label,confidence='BACKBEAT_SNARE',.84
        elif note.note in (49,52,55,57) and _near_boundary(note.onset,boundaries,max(1,tpb//4)):label,confidence='TRANSITION_CYMBAL',.76
        elif len(beat_groups[note.onset//max(1,tpb)])>=5 and _near_boundary(note.onset,boundaries,tpb):label,confidence='FILL_RUN_CANDIDATE',.70
        else:label,confidence='SUBDIVISION_OR_SECONDARY_HIT',.58
        rows.append(_row(note,family,label,confidence,{'beat_index':beat,'notes_in_beat':len(beat_groups[note.onset//max(1,tpb)]),'velocity':note.velocity,'near_section_boundary':_near_boundary(note.onset,boundaries,tpb)},deps,'E2' if family=='DRUM_KIT' else 'E1'))
    return rows


def _bass_rows(notes,tpb,ctx):
    rows=[];arr=sorted(notes,key=lambda item:(item.onset,item.note,item.occurrence))
    for index,note in enumerate(arr):
        prev=arr[index-1] if index else None;nxt=arr[index+1] if index+1<len(arr) else None;deps=[]
        if ctx.identity.rx_named or ctx.identity.dnc_named:deps.append('RX_DNC_IDENTITY')
        if note.velocity<=20:deps.append('LOW_VELOCITY_SPECIAL_CANDIDATE')
        if prev and prev.note==note.note:label,confidence='REPEATED_OR_PEDAL_TONE',.76
        elif prev and nxt and abs(note.note-prev.note)<=2 and abs(nxt.note-note.note)<=2:label,confidence='PASSING_TONE_CANDIDATE',.74
        elif nxt and abs(nxt.note-note.note)<=2:label,confidence='APPROACH_TONE_CANDIDATE',.68
        elif note.onset%max(1,tpb)==0:label,confidence='METRIC_FOUNDATION_ANCHOR',.82
        else:label,confidence='FOUNDATION_LINE_TONE',.60
        rows.append(_row(note,'BASS',label,confidence,{'previous_interval':None if prev is None else note.note-prev.note,'next_interval':None if nxt is None else nxt.note-note.note,'metric_tick':note.onset%max(1,tpb),'velocity':note.velocity},deps,'E2' if str(ctx.role).upper()=='BASS' else 'E1'))
    return rows


def _guitar_rows(notes,tpb,ctx):
    rows=[];window=max(1,tpb//16);clusters=_clusters(notes,window);cluster_for={_key(note):cluster for cluster in clusters for note in cluster};pitch_counts=Counter(note.note for note in notes);unique_ratio=len(pitch_counts)/max(1,len(notes))
    for note in notes:
        cluster=cluster_for[_key(note)];span=max(item.onset for item in cluster)-min(item.onset for item in cluster);deps=[]
        if ctx.identity.rx_named or ctx.identity.dnc_named:deps.append('RX_DNC_GUITAR_ARTICULATION')
        if note.velocity<=20:deps.append('LOW_VELOCITY_NOISE_CANDIDATE')
        if len(cluster)>=3 and span==0:label,confidence='SIMULTANEOUS_CHORD_STRUM',.84
        elif len(cluster)>=3 and span<=window:
            ordered=sorted(cluster,key=lambda item:(item.onset,item.note));direction='ASCENDING' if ordered[-1].note>ordered[0].note else 'DESCENDING';label,confidence=f'ORDERED_{direction}_STRUM_CANDIDATE',.76
        elif unique_ratio<=.35 or pitch_counts[note.note]>=3:label,confidence='RIFF_OSTINATO_TONE',.70
        elif len(cluster)>=2:label,confidence='ARPEGGIATED_CHORD_TONE',.66
        else:label,confidence='SINGLE_NOTE_LINE',.58
        rows.append(_row(note,'GUITAR',label,confidence,{'cluster_notes':len(cluster),'cluster_span_ticks':span,'track_unique_pitch_ratio':round(unique_ratio,4),'pitch_occurrences':pitch_counts[note.note]},deps))
    return rows


def _piano_rows(notes,tpb,ctx,states):
    rows=[];exact=defaultdict(list);near_clusters=_clusters(notes,max(1,tpb//16));near_for={_key(note):cluster for cluster in near_clusters for note in cluster}
    for note in notes:exact[note.onset].append(note)
    for note in notes:
        group=exact[note.onset];near=near_for[_key(note)];state=states.get((note.track_index,note.channel,note.on_index),{});deps=list(state.get('expressive',[]));damper=bool(state.get('damper_active'))
        if damper and 'CC64' not in deps:deps.append('CC64')
        if len(group)>=2:
            pitches=sorted(item.note for item in group)
            if note.note==pitches[-1]:label='CHORD_TOP_VOICE'
            elif note.note==pitches[0]:label='CHORD_BASS_VOICE'
            else:label='CHORD_INNER_VOICE'
            confidence=.84
        elif len(near)>=3:label,confidence='ARPEGGIATED_CHORD_TONE',.72
        else:label,confidence='MELODY_OR_SINGLE_LINE',.58
        rows.append(_row(note,'PIANO_EP',label,confidence,{'simultaneous_group_size':len(group),'near_group_size':len(near),'damper_active':damper,'metric_tick':note.onset%max(1,tpb)},deps))
    return rows


def family_intent_digest(report):
    payload={key:value for key,value in report.items() if key!='digest'};return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def analyze_family_intents(mid,notes,contexts,musical_context,section_narrative=None):
    by_key=defaultdict(list)
    for note in notes:by_key[(note.track_index,note.channel)].append(note)
    states=_controller_states(mid);boundaries=_section_boundaries(musical_context,section_narrative);rows=[];contexts_report=[]
    for key,arr in sorted(by_key.items()):
        ctx=contexts.get(key);family=str((ctx.family if ctx else 'UNKNOWN') or 'UNKNOWN').upper();role=str((ctx.role if ctx else 'UNKNOWN') or 'UNKNOWN').upper();modeled=family in MODELED_FAMILIES or role in ('DRUM','PERC','BASS')
        if role=='DRUM' or family=='DRUM_KIT':family_rows=_drum_rows(arr,mid.ticks_per_beat,boundaries,'DRUM_KIT')
        elif role=='PERC' or family=='PERCUSSION':family_rows=_drum_rows(arr,mid.ticks_per_beat,boundaries,'PERCUSSION')
        elif role=='BASS' or family=='BASS':family_rows=_bass_rows(arr,mid.ticks_per_beat,ctx)
        elif family=='GUITAR':family_rows=_guitar_rows(arr,mid.ticks_per_beat,ctx)
        elif family in ('PIANO','ELECTRIC_PIANO'):family_rows=_piano_rows(arr,mid.ticks_per_beat,ctx,states)
        else:family_rows=[]
        rows.extend(family_rows);contexts_report.append({'track':key[0],'channel':key[1]+1,'family':family,'role':role,'modeled':modeled,'notes':len(arr),'classified_notes':len(family_rows),'coverage':round(len(family_rows)/max(1,len(arr)),4)})
    counts=Counter(row['family'] for row in rows);labels=Counter(row['label'] for row in rows);report={'schema':'PA800_FAMILY_INTENT_V1','analyzer_only':True,'mutations':0,'authority_granted':False,'modeled_families':sorted(MODELED_FAMILIES),'contexts':contexts_report,'note_intents':rows,'summary':{'input_notes':len(notes),'classified_notes':len(rows),'coverage_percent':round(100*len(rows)/max(1,len(notes)),3),'by_family':dict(sorted(counts.items())),'by_label':dict(sorted(labels.items())),'protected_rows':sum(bool(row['protected_dependencies']) for row in rows)},'automation':{'applied_actions':0,'policy':'ANALYZER_ONLY_UNTIL_GROUND_TRUTH_PASS'}}
    report['digest']=family_intent_digest(report);return report


def render_family_intent_summary(report):
    summary=report.get('summary',{});lines=['Family Intent V1','-'*72,f"Classified notes: {summary.get('classified_notes',0)}/{summary.get('input_notes',0)}"]
    for family,count in summary.get('by_family',{}).items():lines.append(f'{family}: {count}')
    lines.append('Authority: analyzer-only');return '\n'.join(lines)+'\n'