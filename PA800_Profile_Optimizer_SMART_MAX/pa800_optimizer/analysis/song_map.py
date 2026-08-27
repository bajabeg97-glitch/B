"""Whole-song map built from existing deterministic musical analyzers.

The map is descriptive only: it records bars, sections, phrases and ensemble
dependencies so a later proposal model can reason beyond neighbouring notes.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')).hexdigest()


def _phrases(notes, sections, track_functions, tpb):
    rows=[];ordinal=0;gap=max(int(tpb*1.5), 1)
    for section in sections:
        start=int(section.get('start_tick', 0));end=int(section.get('end_tick', start));by_context=defaultdict(list)
        for note in notes:
            if start <= note.onset < end:by_context[(note.track_index, note.channel)].append(note)
        for key,group in sorted(by_context.items()):
            group=sorted(group,key=lambda note:(note.onset,note.note,note.occurrence));left=0
            for index in range(1,len(group)+1):
                split=index==len(group) or group[index].onset-group[index-1].off>=gap
                if not split:continue
                chunk=group[left:index];left=index
                rows.append({'id':'phrase:%d'%ordinal,'section_index':section.get('index'),'track':key[0],'channel':key[1]+1,'function':track_functions.get(key,{}).get('function','UNKNOWN'),'start_tick':chunk[0].onset,'end_tick':max(note.off for note in chunk),'notes':len(chunk),'protected_notes':sum(bool(note.protected) for note in chunk),'evidence_level':'E1','mutation_authority':False})
                ordinal+=1
    return rows


def _dependencies(notes, sections, track_functions, tpb):
    rows=[]
    for section in sections:
        start=int(section.get('start_tick',0));end=int(section.get('end_tick',start));by_key=defaultdict(list)
        for note in notes:
            if start<=note.onset<end:by_key[(note.track_index,note.channel)].append(note)
        drums=[key for key in by_key if track_functions.get(key,{}).get('function') in ('FOUNDATION_DRUM','FOUNDATION_PERC')]
        basses=[key for key in by_key if track_functions.get(key,{}).get('function')=='FOUNDATION_BASS']
        for drum in drums:
            for bass in basses:
                drum_onsets={note.onset for note in by_key[drum]};bass_onsets={note.onset for note in by_key[bass]};shared=len(drum_onsets&bass_onsets)
                rows.append({'kind':'DRUM_BASS_GROOVE_LOCK','section_index':section.get('index'),'contexts':[[drum[0],drum[1]+1],[bass[0],bass[1]+1]],'shared_onsets':shared,'evidence_level':'E1','policy':'PRESERVE_MEASURED_OFFSET','mutation_authority':False})
        simultaneous=defaultdict(list)
        for key,group in by_key.items():
            function=track_functions.get(key,{}).get('function','UNKNOWN')
            if function in ('HARMONIC_COMP','PAD_BACKGROUND','LEAD','COUNTER_LINE'):
                for note in group:simultaneous[note.onset].append((key,note))
        chord_groups=sum(1 for group in simultaneous.values() if len(group)>=2)
        if chord_groups:
            rows.append({'kind':'CHORD_GROUP_COHERENCE','section_index':section.get('index'),'chord_groups':chord_groups,'evidence_level':'E1','policy':'PRESERVE_SIMULTANEITY_AND_RELATIVE_BALANCE','mutation_authority':False})
    return rows


def _build_song_map(notes, musical_context, narrative, instrument_intent):
    sections=[]
    for row in narrative.get('sections') or musical_context.get('sections',[]):
        sections.append({'index':row.get('index'),'label':row.get('label','UNKNOWN'),'start_tick':row.get('start_tick',0),'end_tick':row.get('end_tick',0),'start_bar':row.get('start_bar'),'end_bar':row.get('end_bar'),'evidence_level':row.get('evidence_level','E0'),'confidence':row.get('confidence',0.0),'mutation_authority':False})
    track_functions={(int(row['track']),int(row['channel'])-1):row for row in musical_context.get('track_functions',[])}
    meter=narrative.get('meter') or {};tpb=max(1,int(meter.get('ticks_per_beat') or round(float(meter.get('bar_ticks',192))*max(1,int(meter.get('denominator',4)))/(max(1,int(meter.get('numerator',4)))*4))))
    phrase_rows=_phrases(notes,sections,track_functions,tpb)
    dependencies=_dependencies(notes,sections,track_functions,1)
    bars=[{'index':row.get('index'),'start_tick':row.get('start_tick'),'end_tick':row.get('end_tick'),'notes':row.get('notes',0),'density_notes_per_beat':row.get('density_notes_per_beat',0),'mutation_authority':False} for row in narrative.get('bars',[])]
    unknown_tracks=int((instrument_intent.get('summary') or {}).get('unknown_tracks',0) or 0)
    payload={'schema':'PA800_SONG_MAP_V1','analyzer_only':True,'authority_granted':False,'mutations':0,'bars':bars,'sections':sections,'phrases':phrase_rows,'track_functions':[track_functions[key] for key in sorted(track_functions)],'dependencies':dependencies,'summary':{'bars':len(bars),'sections':len(sections),'phrases':len(phrase_rows),'dependencies':len(dependencies),'unknown_tracks':unknown_tracks},'limits':['Map is descriptive context, not edit authority.','Protected note, RX/DNC and controller constraints remain owned by the safety kernel.']}
    return {**payload,'digest':_digest(payload)}