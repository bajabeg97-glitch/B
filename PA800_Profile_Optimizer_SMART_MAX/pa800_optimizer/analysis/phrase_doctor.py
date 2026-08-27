"""Conservative phrase-level anomaly detector; it never edits MIDI."""
from __future__ import annotations

import hashlib
import json
import statistics


def _median(values, default=0.0):
    return float(statistics.median(values)) if values else float(default)


def _mad(values, center):
    return _median([abs(value-center) for value in values])


def _digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def _analyze_phrase_doctor(notes, song_map, ticks_per_beat):
    """Mark conspicuous phrase outliers as suggestions, never repair targets."""
    findings=[];tpb=max(1,int(ticks_per_beat))
    for phrase in song_map.get('phrases',[]):
        track=int(phrase['track']);channel=int(phrase['channel'])-1;start=int(phrase['start_tick']);end=int(phrase['end_tick'])
        group=sorted([note for note in notes if note.track_index==track and note.channel==channel and start<=note.onset<=end],key=lambda note:(note.onset,note.note,note.occurrence))
        editable=[note for note in group if not note.protected]
        if len(editable)<4:continue
        velocities=[note.velocity for note in editable];center=_median(velocities);spread=_mad(velocities,center);velocity_limit=max(18.0,3.0*spread)
        durations=[note.duration for note in editable];duration_center=_median(durations);duration_spread=_mad(durations,duration_center);short_limit=max(1.0,duration_center-3.0*duration_spread)
        for note in editable:
            if abs(note.velocity-center)>velocity_limit:
                findings.append({'phrase_id':phrase['id'],'kind':'VELOCITY_ANOMALY','severity':'warning','event_key':[note.track_index,note.channel+1,note.onset,note.note,note.occurrence],'reason':'Velocity differs materially from its local phrase distribution.','confidence':0.72,'uncertainty':0.28,'reference_value':round(center,3),'candidate_delta':None,'requested_action':'SUGGEST','protected_dependencies':[]})
            if note.duration<short_limit and duration_center>=tpb*.18:
                findings.append({'phrase_id':phrase['id'],'kind':'GATE_ANOMALY','severity':'warning','event_key':[note.track_index,note.channel+1,note.onset,note.note,note.occurrence],'reason':'Duration is materially shorter than neighbouring phrase notes.','confidence':0.64,'uncertainty':0.36,'reference_value':round(duration_center,3),'candidate_delta':None,'requested_action':'SUGGEST','protected_dependencies':[]})
        gaps=[b.onset-a.onset for a,b in zip(editable,editable[1:])]
        if len(gaps)>=3:
            gap_center=_median(gaps);gap_spread=_mad(gaps,gap_center);gap_limit=max(tpb*.5,3.0*gap_spread)
            for previous,current in zip(editable,editable[1:]):
                if abs((current.onset-previous.onset)-gap_center)>gap_limit:
                    findings.append({'phrase_id':phrase['id'],'kind':'TIMING_GAP_ANOMALY','severity':'info','event_key':[current.track_index,current.channel+1,current.onset,current.note,current.occurrence],'reason':'Onset gap differs from local phrase spacing; preserve if it is intentional rubato, flam or pickup.','confidence':0.52,'uncertainty':0.48,'candidate_delta':None,'requested_action':'SUGGEST','protected_dependencies':[]})
    payload={'schema':'PA800_PHRASE_DOCTOR_V1','analyzer_only':True,'authority_granted':False,'mutations':0,'applied_actions':0,'findings':findings,'summary':{'phrases_considered':len(song_map.get('phrases',[])),'findings':len(findings),'velocity_anomalies':sum(row['kind']=='VELOCITY_ANOMALY' for row in findings),'gate_anomalies':sum(row['kind']=='GATE_ANOMALY' for row in findings),'timing_gap_anomalies':sum(row['kind']=='TIMING_GAP_ANOMALY' for row in findings),'protected_events_proposed':0},'limits':['Shadow analysis only; no MIDI event is changed.','Intentional flam, rubato, ghost notes and pickups require musician confirmation.']}
    return {**payload,'digest':_digest(payload)}