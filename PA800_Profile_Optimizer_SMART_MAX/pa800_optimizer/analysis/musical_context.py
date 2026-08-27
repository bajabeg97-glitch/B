"""Analyzer-only musical context model for sections, track function and balance.

This module never mutates MIDI events.  Its first responsibility is to expose
what is observed, what is heuristic, and how confident each musical inference
is before later releases are allowed to use it as optimization authority.
"""
from __future__ import annotations

from collections import Counter,defaultdict
import math,statistics

from .meter_map import _build_bar_spans,_meter_changes


EVIDENCE_LABELS={
    'E0':'UNKNOWN / preserve',
    'E1':'HEURISTIC / analyzer or suggestion',
    'E2':'FACTORY or serialized structural evidence',
    'E3':'hardware-confirmed evidence',
}

FOUNDATION={'FOUNDATION_DRUM','FOUNDATION_PERC','FOUNDATION_BASS'}
BACKGROUND={'HARMONIC_COMP','PAD_BACKGROUND'}
FOREGROUND={'LEAD','COUNTER_LINE','RIFF_OSTINATO'}


def evidence_for_context(ctx):
    if not ctx or ctx.identity.conflict:return 'E0'
    status=str(ctx.resolution_status or '')
    if status.startswith('EXACT') and None not in ctx.identity.address():return 'E2'
    if ctx.family and ctx.family!='UNKNOWN':return 'E1'
    return 'E0'


def _median(values,default=0.0):return float(statistics.median(values)) if values else float(default)


def _overlap(a0,a1,b0,b1):
    inter=max(0,min(a1,b1)-max(a0,b0)+1);union=max(a1,b1)-min(a0,b0)+1
    return inter/max(1,union)


def _first_meter(mid):
    for track in mid.tracks:
        for msg in track:
            if msg.type=='time_signature':
                numerator=max(1,int(getattr(msg,'numerator',4)));denominator=max(1,int(getattr(msg,'denominator',4)))
                return numerator,denominator
    return 4,4


def _controller_energy_by_index(track,channel):
    volume=100;expression=127;result={}
    for index,msg in enumerate(track):
        if getattr(msg,'channel',None)!=channel:continue
        if msg.type=='control_change' and msg.control==7:volume=msg.value
        elif msg.type=='control_change' and msg.control==11:expression=msg.value
        elif msg.type=='note_on' and msg.velocity>0:result[index]=math.sqrt(max(.01,(volume/100.0)*(expression/127.0)))
    return result


def classify_track_function(ctx,notes,tpb):
    family=str(ctx.family or 'UNKNOWN').upper();role=str(ctx.role or 'UNKNOWN').upper();name=str(ctx.track_name or ctx.identity.name or '').lower();tpb=max(1,tpb)
    onsets=Counter(n.onset for n in notes);chord_notes=sum(count for count in onsets.values() if count>1);chord_fraction=chord_notes/max(1,len(notes));polyphony=_median(list(onsets.values()),1)
    durations=[n.duration/tpb for n in notes];duration=_median(durations);pitches=[n.note for n in notes];pitch_min=min(pitches) if pitches else None;pitch_max=max(pitches) if pitches else None;pitch_center=_median(pitches,60);unique_ratio=len(set(pitches))/max(1,len(pitches));repeat_fraction=sum(a.note==b.note for a,b in zip(notes,notes[1:]))/max(1,len(notes)-1)
    span=max(tpb,(max((n.off for n in notes),default=tpb)-min((n.onset for n in notes),default=0)));density=len(notes)/(span/tpb);monophonic_fraction=sum(count==1 for count in onsets.values())/max(1,len(onsets))
    reasons=[];evidence='E1';function='UNKNOWN'
    if role=='DRUM' or family=='DRUM_KIT':function='FOUNDATION_DRUM';evidence='E2';reasons.append('serialized_drum_role_or_kit')
    elif role=='PERC':function='FOUNDATION_PERC';evidence='E2';reasons.append('serialized_percussion_role')
    elif role=='BASS' or family=='BASS':function='FOUNDATION_BASS';evidence='E2' if role=='BASS' else 'E1';reasons.append('bass_role_or_family')
    elif any(word in name for word in ('lead','solo','melody','vocal')):function='LEAD';reasons.append('track_name_lead_marker')
    elif family in ('SFX','SYNTH_FX') or any(word in name for word in ('fx','noise','effect')):function='ORNAMENT_FX';reasons.append('effect_family_or_name')
    elif family in ('SYNTH_PAD','STRINGS','ENSEMBLE') and duration>=.75 and chord_fraction>=.35:function='PAD_BACKGROUND';reasons.append('sustained_polyphonic_texture')
    elif chord_fraction>=.55 or (polyphony>=2 and duration>=.25):function='HARMONIC_COMP';reasons.append('polyphonic_harmonic_texture')
    elif repeat_fraction>=.30 or (unique_ratio<=.18 and density>=1.5):function='RIFF_OSTINATO';reasons.append('repetition_and_density')
    elif monophonic_fraction>=.82 and pitch_center>=55 and duration<=1.5:function='LEAD';reasons.append('monophonic_foreground_shape')
    elif monophonic_fraction>=.70:function='COUNTER_LINE';reasons.append('mostly_monophonic_secondary_line')
    elif notes:function='HARMONIC_COMP';reasons.append('bounded_accompaniment_fallback')
    else:function='UNKNOWN';evidence='E0';reasons.append('no_note_evidence')
    raw_conf=.35
    if evidence=='E2':raw_conf=.98
    elif function!='UNKNOWN':raw_conf=.58+min(.18,len(notes)/1000)+(.10 if reasons and 'track_name' in reasons[0] else 0)+(.08 if family!='UNKNOWN' else 0)
    confidence=max(0.0,min(.95,raw_conf)) if evidence!='E2' else raw_conf
    return {'track':ctx.track_index,'channel':ctx.channel+1,'role':ctx.role,'family':ctx.family,'sound':ctx.identity.name,'function':function,'confidence':round(confidence,3),'evidence_level':evidence,'evidence_label':EVIDENCE_LABELS[evidence],'reasons':reasons,'features':{'notes':len(notes),'density_notes_per_beat':round(density,4),'median_duration_beats':round(duration,4),'chord_note_fraction':round(chord_fraction,4),'median_onset_polyphony':round(polyphony,3),'monophonic_fraction':round(monophonic_fraction,4),'repeat_fraction':round(repeat_fraction,4),'unique_pitch_ratio':round(unique_ratio,4),'pitch_min':pitch_min,'pitch_max':pitch_max,'pitch_center':round(pitch_center,3)}}


def _song_sections(mid,notes,track_functions,tpb):
    changes=_meter_changes(mid);first=changes[0];default_bar_ticks=max(1,int(round(tpb*first['numerator']*4/first['denominator'])));end=max((n.off for n in notes),default=default_bar_ticks);bar_rows=_build_bar_spans(mid,end);bars=len(bar_rows);window_bars=4 if bars>=12 else 2 if bars>=5 else 1;windows=[]
    for left in range(0,bars,window_bars):
        chunk=bar_rows[left:left+window_bars];start=chunk[0]['start_tick'];stop=chunk[-1]['end_tick'];arr=[n for n in notes if start<=n.onset<stop];tracks={(n.track_index,n.channel) for n in arr};vel=_median([n.velocity for n in arr]);density=len(arr)/max(1,(stop-start)/tpb);functions=Counter(track_functions.get(key,{}).get('function','UNKNOWN') for key in tracks)
        windows.append({'start_tick':start,'end_tick':stop,'start_bar':left+1,'end_bar':left+len(chunk),'notes':len(arr),'active_tracks':tracks,'density':density,'velocity':vel,'functions':functions})
    boundaries=[0]
    for i in range(1,len(windows)):
        a,b=windows[i-1],windows[i];union=a['active_tracks']|b['active_tracks'];jaccard=len(a['active_tracks']&b['active_tracks'])/max(1,len(union));density_change=abs(b['density']-a['density'])/max(.25,a['density'],b['density']);velocity_change=abs(b['velocity']-a['velocity'])/127;score=.55*(1-jaccard)+.35*min(1,density_change)+.10*velocity_change
        if score>=.34:boundaries.append(i)
    boundaries.append(len(windows));segments=[]
    for si,(left,right) in enumerate(zip(boundaries,boundaries[1:])):
        chunk=windows[left:right];start=chunk[0]['start_tick'];stop=chunk[-1]['end_tick'];note_count=sum(x['notes'] for x in chunk);density=sum(x['density'] for x in chunk)/len(chunk);velocity=sum(x['velocity'] for x in chunk)/len(chunk);active=set().union(*(x['active_tracks'] for x in chunk));func=Counter();[func.update(x['functions']) for x in chunk]
        segments.append({'index':si,'start_tick':start,'end_tick':stop,'start_bar':chunk[0]['start_bar'],'end_bar':chunk[-1]['end_bar'],'notes':note_count,'density_notes_per_beat':round(density,4),'velocity_median_proxy':round(velocity,3),'active_tracks':len(active),'function_presence':dict(func)})
    densities=[s['density_notes_per_beat'] for s in segments];median_density=_median(densities,0);max_density=max(densities,default=0)
    for i,segment in enumerate(segments):
        if len(segments)==1:label='WHOLE_SONG';confidence=.55
        elif i==0:label='INTRO';confidence=.72
        elif i==len(segments)-1:label='ENDING';confidence=.72
        elif segment['density_notes_per_beat']<median_density*.55:label='BREAK';confidence=.68
        elif max_density and segment['density_notes_per_beat']>=max_density*.90:label='CHORUS';confidence=.62
        elif segment['function_presence'].get('LEAD',0)==1 and segment['function_presence'].get('HARMONIC_COMP',0)<=1:label='SOLO';confidence=.58
        else:label='VERSE_OR_BODY';confidence=.52
        segment.update({'label':label,'confidence':confidence,'evidence_level':'E1','evidence_label':EVIDENCE_LABELS['E1']})
    return segments,{'meter':[first['numerator'],first['denominator']],'bar_ticks':default_bar_ticks,'meter_changes':changes,'bar_count':bars,'window_bars':window_bars,'method':'activity/density/register-free change point heuristic'}


def _style_sections(notes_by_key,contexts):
    grouped=defaultdict(list)
    for key,arr in notes_by_key.items():
        ctx=contexts.get(key)
        if ctx and ctx.element:grouped[(ctx.element,ctx.cv)].extend(arr)
    rows=[]
    for index,((element,cv),arr) in enumerate(sorted(grouped.items(),key=lambda x:(str(x[0][0]),int(x[0][1] or 0)))):
        rows.append({'index':index,'label':element,'cv':cv,'start_tick':min((n.onset for n in arr),default=0),'end_tick':max((n.off for n in arr),default=0),'notes':len(arr),'active_tracks':len({(n.track_index,n.channel) for n in arr}),'confidence':.99,'evidence_level':'E2','evidence_label':EVIDENCE_LABELS['E2']})
    if not rows:
        all_notes=[note for arr in notes_by_key.values() for note in arr]
        rows=[{'index':0,'label':'STYLE_WHOLE_UNLABELED','cv':None,'start_tick':min((n.onset for n in all_notes),default=0),'end_tick':max((n.off for n in all_notes),default=0),'notes':len(all_notes),'active_tracks':len(notes_by_key),'confidence':.35,'evidence_level':'E0','evidence_label':EVIDENCE_LABELS['E0']}]
        return rows,{'method':'Style-like structure detected but no serialized Element label; preserve/ground-truth required'}
    return rows,{'method':'serialized Style Element/CV labels'}


def _ensemble_sections(mid,notes,sections,track_functions,tpb):
    controller={key:_controller_energy_by_index(mid.tracks[key[0]],key[1]) for key in track_functions};rows=[]
    for section in sections:
        start,end=section['start_tick'],section['end_tick'];by_track=defaultdict(list)
        for note in notes:
            if start<=note.onset<end:by_track[(note.track_index,note.channel)].append(note)
        parts=[]
        for key,arr in by_track.items():
            tf=track_functions.get(key,{});scales=controller.get(key,{});energy=_median([n.velocity*scales.get(n.on_index,1.0) for n in arr]);pitches=[n.note for n in arr];span=max(tpb,end-start);density=len(arr)/(span/tpb);boost=1.25 if tf.get('function')=='LEAD' else 1.12 if tf.get('function') in FOREGROUND else .92 if tf.get('function') in BACKGROUND else 1.0;salience=energy*boost*math.log2(2+len(arr))
            parts.append({'track':key[0],'channel':key[1]+1,'function':tf.get('function','UNKNOWN'),'family':tf.get('family'),'sound':tf.get('sound'),'notes':len(arr),'density':round(density,4),'energy':round(energy,3),'pitch_min':min(pitches),'pitch_max':max(pitches),'salience':round(salience,3)})
        parts.sort(key=lambda x:x['salience'],reverse=True);focus=parts[0] if parts else None;alerts=[]
        for i,a in enumerate(parts):
            for b in parts[i+1:]:
                overlap=_overlap(a['pitch_min'],a['pitch_max'],b['pitch_min'],b['pitch_max'])
                if overlap>=.65 and min(a['density'],b['density'])>=.5 and a['function'] not in FOUNDATION and b['function'] not in FOUNDATION:
                    alerts.append({'kind':'REGISTER_DENSITY_MASKING','tracks':[[a['track'],a['channel']],[b['track'],b['channel']]],'overlap':round(overlap,3),'evidence_level':'E1'})
        background=[p['energy'] for p in parts if p['function'] in BACKGROUND];focus_margin=None if not focus or not background else focus['energy']-_median(background);status='NO_ACTIVE_NOTES' if not parts else 'FOCUS_UNCLEAR' if focus and focus['function'] in BACKGROUND and len(parts)>2 else 'MASKING_RISK' if alerts else 'BALANCED_OR_UNPROVEN'
        rows.append({'section_index':section['index'],'section_label':section['label'],'focus':focus,'focus_energy_margin_over_background':None if focus_margin is None else round(focus_margin,3),'parts':parts,'masking_alerts':alerts,'status':status,'evidence_level':'E1','mutations':0})
    return rows


def analyze_musical_context(mid,notes,contexts,content_type):
    notes_by_key=defaultdict(list)
    for note in notes:notes_by_key[(note.track_index,note.channel)].append(note)
    functions={}
    for key,ctx in contexts.items():functions[key]=classify_track_function(ctx,notes_by_key.get(key,[]),mid.ticks_per_beat)
    meter=_first_meter(mid)
    if content_type=='style':sections,section_basis=_style_sections(notes_by_key,contexts)
    else:sections,section_basis=_song_sections(mid,notes,functions,mid.ticks_per_beat)
    ensemble=_ensemble_sections(mid,notes,sections,functions,mid.ticks_per_beat)
    counts=Counter(row['function'] for row in functions.values());evidence=Counter(row['evidence_level'] for row in functions.values())
    return {'schema':'PA800_MUSICAL_CONTEXT_V1','analyzer_only':True,'mutations':0,'content_type':content_type,'evidence_levels':EVIDENCE_LABELS,'meter':{'numerator':meter[0],'denominator':meter[1],'changes':_meter_changes(mid)},'section_basis':section_basis,'sections':sections,'track_functions':[functions[key] for key in sorted(functions)],'function_counts':dict(counts),'function_evidence_counts':dict(evidence),'ensemble_sections':ensemble,'summary':{'sections':len(sections),'tracks':len(functions),'masking_alerts':sum(len(row['masking_alerts']) for row in ensemble),'unknown_functions':counts.get('UNKNOWN',0)}}