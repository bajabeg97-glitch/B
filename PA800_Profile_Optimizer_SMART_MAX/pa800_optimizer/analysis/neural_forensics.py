"""Independent forensic and musical-invariant audit for neural MIDI output."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from ..core.midi_io import absolute_track,extract_notes,load_midi

ALLOWED_NEURAL_CHANGE_KINDS={'timing','gate'}
VOICE_CONTROLS={0,32,80,81}


def _mid(value):return load_midi(Path(value)) if isinstance(value,(str,Path)) else value


def _notes(mid):
    return {(row.track_index,row.channel,row.note,row.occurrence):row for row in extract_notes(mid)}


def _non_note_events(mid):
    rows=[]
    for track_index,track in enumerate(mid.tracks):
        for tick,ordinal,message in absolute_track(track):
            if message.type in ('note_on','note_off'):continue
            data=message.dict();data.pop('time',None);rows.append((track_index,tick,message.type,repr(sorted(data.items()))))
    return rows


def _voice_events(mid):
    rows=[]
    for track_index,track in enumerate(mid.tracks):
        for tick,ordinal,message in absolute_track(track):
            if message.type=='program_change' or (message.type=='control_change' and message.control in VOICE_CONTROLS):rows.append((track_index,tick,message.type,getattr(message,'channel',None),getattr(message,'control',None),getattr(message,'value',None),getattr(message,'program',None)))
    return rows


def _track_ends(mid):return [max((tick for tick,_ordinal,_message in absolute_track(track)),default=0) for track in mid.tracks]


def audit_neural_application(before,after,report=None):
    """Fail closed unless output is a bounded timing/gate-only musical edit."""
    before=_mid(before);after=_mid(after);left=_notes(before);right=_notes(after);errors=[];tpb=max(1,int(before.ticks_per_beat))
    if before.type!=after.type:errors.append('smf_type_changed')
    if before.ticks_per_beat!=after.ticks_per_beat:errors.append('ticks_per_beat_changed')
    if len(before.tracks)!=len(after.tracks):errors.append('track_count_changed')
    if _track_ends(before)!=_track_ends(after):errors.append('track_end_changed')
    if set(left)!=set(right):errors.append('note_identity_changed')
    common=sorted(set(left)&set(right));onset_deltas=[];off_deltas=[]
    for key in common:
        a=left[key];b=right[key]
        if a.note!=b.note:errors.append('pitch_changed:'+repr(key))
        if a.velocity!=b.velocity:errors.append('velocity_changed:'+repr(key))
        if b.off<=b.onset and a.off>a.onset:errors.append('non_positive_duration:'+repr(key))
        onset_deltas.append(abs(b.onset-a.onset));off_deltas.append(abs(b.off-a.off))
    if max(onset_deltas,default=0)>max(1,tpb//8):errors.append('onset_delta_over_bound')
    if max(off_deltas,default=0)>max(1,tpb//4):errors.append('off_delta_over_bound')
    if _voice_events(before)!=_voice_events(after):errors.append('voice_events_changed')
    if _non_note_events(before)!=_non_note_events(after):errors.append('non_note_events_changed')
    before_groups=defaultdict(list)
    for key,row in left.items():before_groups[(row.track_index,row.channel,row.onset)].append(key)
    broken_chords=0
    for keys in before_groups.values():
        if len(keys)<2 or any(key not in right for key in keys):continue
        if len({right[key].onset for key in keys})!=1:broken_chords+=1
    if broken_chords:errors.append('simultaneous_group_broken')
    before_order=defaultdict(list);after_order=defaultdict(list)
    for key,row in left.items():before_order[(row.track_index,row.channel)].append((row.onset,key))
    for key,row in right.items():after_order[(row.track_index,row.channel)].append((row.onset,key))
    order_changes=0
    for context,rows in before_order.items():
        old=[key for _tick,key in sorted(rows)];new=[key for _tick,key in sorted(after_order.get(context,()))]
        if old!=new:order_changes+=1
    if order_changes:errors.append('phrase_note_order_changed')
    changes=list(getattr(report,'changes',[]) if report is not None else [])
    illegal=sorted({getattr(row,'kind',None) for row in changes if getattr(row,'kind',None) not in ALLOWED_NEURAL_CHANGE_KINDS})
    if illegal:errors.append('illegal_reported_change_kinds')
    if report is not None:
        boundary=((getattr(report,'quality_gate',{}) or {}).get('neural_factory_boundary') or {})
        if not boundary.get('pass'):errors.append('authority_boundary_failed')
        verifier=getattr(report,'verifier',{}) or {}
        if not verifier.get('pass'):errors.append('canonical_verifier_failed')
    return {'schema':'PA800_NEURAL_APPLICATION_FORENSIC_V1','pass':not errors,'errors':errors,'notes':len(common),'tracks':len(before.tracks),'max_onset_delta':max(onset_deltas,default=0),'max_off_delta':max(off_deltas,default=0),'simultaneous_groups':sum(len(keys)>=2 for keys in before_groups.values()),'broken_simultaneous_groups':broken_chords,'phrase_order_changes':order_changes,'voice_events_preserved':_voice_events(before)==_voice_events(after),'non_note_events_preserved':_non_note_events(before)==_non_note_events(after),'velocity_preserved':all(left[key].velocity==right[key].velocity for key in common),'pitch_preserved':set(left)==set(right),'allowed_change_kinds':sorted(ALLOWED_NEURAL_CHANGE_KINDS),'reported_change_kinds':sorted({getattr(row,'kind',None) for row in changes if getattr(row,'kind',None) is not None})}