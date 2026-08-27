"""Conservative instrument-family guards shared by the 2.4A note engines."""
from __future__ import annotations

from collections import defaultdict
import statistics

from .policies import normalized_family


SUSTAINED_FAMILIES={'STRINGS','ENSEMBLE','SYNTH_PAD','CHOIR_VOICE'}
EXPRESSIVE_FAMILIES={'BRASS','REED','PIPE','HARMONICA','ACCORDION','SYNTH_LEAD'}
EXPRESSIVE_CONTROLS={1,2,64,80,81}


def note_id(note):
    return (note.track_index,note.channel,note.note,note.occurrence)


def near_onset_groups(notes,window_ticks,minimum=2):
    arr=sorted(notes,key=lambda n:(n.onset,n.note,n.occurrence));groups=[];current=[]
    for note in arr:
        if not current or note.onset-current[-1].onset<=window_ticks:current.append(note)
        else:
            if len(current)>=minimum:groups.append(current)
            current=[note]
    if len(current)>=minimum:groups.append(current)
    return groups


def exact_onset_groups(notes,minimum=2):
    grouped=defaultdict(list)
    for note in notes:grouped[note.onset].append(note)
    return [grouped[onset] for onset in sorted(grouped) if len(grouped[onset])>=minimum]


def phrase_groups(notes,tpb,minimum=2):
    """Split one track/channel into bounded phrases at musically meaningful rests.

    This is deliberately descriptive: it never joins across a rest of one beat
    or more, and it does not infer harmony, breath marks or author intent.
    """
    arr=sorted(notes,key=lambda n:(n.onset,n.note,n.occurrence))
    if not arr:return []
    durations=[max(1,n.off-n.onset) for n in arr]
    rest_threshold=max(1,int(tpb),int(statistics.median(durations)))
    groups=[];current=[arr[0]];phrase_end=arr[0].off
    for note in arr[1:]:
        if note.onset-phrase_end>=rest_threshold:
            if len(current)>=minimum:groups.append(current)
            current=[note]
        else:current.append(note)
        phrase_end=max(phrase_end,note.off)
    if len(current)>=minimum:groups.append(current)
    return groups


def timing_guard_ids(notes,contexts,tpb):
    by_context=defaultdict(list)
    for note in notes:by_context[(note.track_index,note.channel)].append(note)
    guitar=set();piano=set()
    for key,arr in by_context.items():
        ctx=contexts.get(key);family=str(ctx.family if ctx else 'UNKNOWN').upper()
        if family=='GUITAR':
            for group in near_onset_groups(arr,max(1,int(tpb)//32)):
                if len({note.note for note in group})>1:guitar.update(note_id(note) for note in group)
        elif family=='PIANO':
            for group in exact_onset_groups(arr):piano.update(note_id(note) for note in group)
    return guitar,piano


def sustained_timing_guard_ids(notes,contexts):
    by_context=defaultdict(list);guarded=set()
    for note in notes:by_context[(note.track_index,note.channel)].append(note)
    for key,arr in by_context.items():
        ctx=contexts.get(key);family=normalized_family(ctx.family if ctx else None)
        if family in SUSTAINED_FAMILIES:
            for group in exact_onset_groups(arr):guarded.update(note_id(note) for note in group)
    return guarded


def sustained_tail_note_ids(notes,contexts,tpb):
    result=set();threshold=max(1,int(tpb*.75))
    for note in notes:
        ctx=contexts.get((note.track_index,note.channel));family=normalized_family(ctx.family if ctx else None)
        duration=getattr(note,'duration',max(0,note.off-note.onset))
        if family in SUSTAINED_FAMILIES and duration>=threshold:result.add(note_id(note))
    return result


def organ_legato_note_ids(notes,contexts):
    by_context=defaultdict(list);result=set()
    for note in notes:by_context[(note.track_index,note.channel)].append(note)
    for key,arr in by_context.items():
        ctx=contexts.get(key)
        if normalized_family(ctx.family if ctx else None)!='ORGAN':continue
        onsets=sorted({note.onset for note in arr})
        for note in arr:
            next_onset=next((onset for onset in onsets if onset>note.onset),None)
            if next_onset is not None and note.off>=next_onset:
                result.add(note_id(note))
                result.update(note_id(candidate) for candidate in arr if candidate.onset==next_onset)
    return result


def ambiguous_occurrence_note_ids(notes):
    """Protect repeated same-pitch streams whose FIFO identity can be reordered."""
    grouped=defaultdict(list);result=set()
    for note in notes:grouped[(note.track_index,note.channel,note.note)].append(note)
    for arr in grouped.values():
        arr=sorted(arr,key=lambda note:(note.onset,note.occurrence))
        if any(current.onset<=previous.off for previous,current in zip(arr,arr[1:])):
            result.update(note_id(note) for note in arr)
    return result


def expressive_controller_channels(mid,contexts):
    guarded=set()
    for track_index,track in enumerate(mid.tracks):
        for msg in track:
            channel=getattr(msg,'channel',None)
            if channel is None:continue
            ctx=contexts.get((track_index,channel));family=normalized_family(ctx.family if ctx else None)
            if family not in EXPRESSIVE_FAMILIES:continue
            if (msg.type=='control_change' and msg.control in EXPRESSIVE_CONTROLS) or msg.type in ('pitchwheel','aftertouch','polytouch'):guarded.add((track_index,channel))
    return guarded


def pedal_held_note_ids(mid,notes,contexts):
    by_track_channel=defaultdict(list)
    for note in notes:
        ctx=contexts.get((note.track_index,note.channel))
        if ctx and str(ctx.family).upper()=='PIANO':by_track_channel[(note.track_index,note.channel)].append(note)
    held=set()
    for (track_index,channel),arr in by_track_channel.items():
        state=False;state_at_index={}
        for index,msg in enumerate(mid.tracks[track_index]):
            if getattr(msg,'channel',None)!=channel:continue
            if msg.type=='control_change' and msg.control==64:state=msg.value>=64
            state_at_index[index]=state
        for note in arr:
            if state_at_index.get(note.on_index,False) or state_at_index.get(note.off_index,False):held.add(note_id(note))
    return held


def retain_group_spread(notes,proposed,minimum=.75,lo=1,hi=127):
    """Blend a proposal back toward source until simultaneous chord spread survives."""
    result=list(proposed);index_by_id={id(note):index for index,note in enumerate(notes)}
    for group in exact_onset_groups(notes):
        indices=[index_by_id[id(note)] for note in group];original=[notes[index].velocity for index in indices];candidate=[result[index] for index in indices]
        original_range=max(original)-min(original);candidate_range=max(candidate)-min(candidate)
        if original_range<=0 or candidate_range+1e-9>=minimum*original_range:continue
        best=list(original)
        low=0.0;high=1.0
        for _ in range(16):
            alpha=(low+high)/2;trial=[int(round(c+(o-c)*alpha)) for o,c in zip(original,candidate)]
            if max(trial)-min(trial)>=minimum*original_range:best=trial;high=alpha
            else:low=alpha
        for index,value in zip(indices,best):result[index]=max(lo,min(hi,value))
    return result


def retain_group_velocity_shape(notes,proposed,groups,lo=1,hi=127):
    """Move a chord/strum coherently while preserving its internal dynamics."""
    result=list(proposed);index_by_id={id(note):index for index,note in enumerate(notes)}
    for group in groups:
        indices=[index_by_id[id(note)] for note in group if id(note) in index_by_id]
        if len(indices)<2:continue
        deltas=sorted(result[index]-notes[index].velocity for index in indices);delta=deltas[len(deltas)//2]
        lower=max(lo-notes[index].velocity for index in indices);upper=min(hi-notes[index].velocity for index in indices);delta=max(lower,min(upper,delta))
        for index in indices:result[index]=int(notes[index].velocity+delta)
    return result