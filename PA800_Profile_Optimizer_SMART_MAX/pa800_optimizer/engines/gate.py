from collections import defaultdict
from ..core.midi_io import absolute_track, rebuild_track
from ..utils import clamp
from ..models import Change
from ..instruments.policies import policy_for,profile_evidence_allows_mutation
from ..instruments.guards import ambiguous_occurrence_note_ids,expressive_controller_channels,note_id,organ_legato_note_ids,pedal_held_note_ids,sustained_tail_note_ids

def optimize_gate(mid, notes, contexts, profiles, config, report):
    if not config.enable_gate or config.gate_strength<=0:return
    pedal_held=pedal_held_note_ids(mid,notes,contexts);sustained=sustained_tail_note_ids(notes,contexts,mid.ticks_per_beat);organ_legato=organ_legato_note_ids(notes,contexts);occurrence_guard=ambiguous_occurrence_note_ids(notes);controller_guard=expressive_controller_channels(mid,contexts)
    by_tc=defaultdict(list)
    for n in notes:
        if not n.protected: by_tc[(n.track_index,n.channel)].append(n)
    track_updates=defaultdict(dict)
    track_ends={}
    for ti in set(n.track_index for n in notes):
        ev=absolute_track(mid.tracks[ti]); track_ends[ti]=max((x[0] for x in ev), default=0)
    for key,arr in by_tc.items():
        ctx=contexts.get(key); p=profiles.get(key)
        if not ctx:continue
        policy=policy_for(ctx.family)
        if not p or not ctx or not policy.get('gate',False) or not profile_evidence_allows_mutation(policy,p):continue
        gate_scale=float(policy.get('gate_scale',1.0))
        if gate_scale<=0:continue
        arr.sort(key=lambda n:(n.onset,n.note)); g=p.get('gate_to_next_onset')
        # Missing/null gate evidence means preserve. Never invent a generic gate
        # target for partial Factory/GM profiles.
        if not isinstance(g,dict) or not g:continue
        try:
            center=float(g.get('ideal_center'));wmin=float(g.get('working_min'));wmax=float(g.get('working_max'))
        except (TypeError,ValueError):continue
        onsets=sorted(set(n.onset for n in arr));same_pitch_onsets=defaultdict(list)
        for item in arr:same_pitch_onsets[item.note].append(item.onset)
        for n in arr:
            if note_id(n) in pedal_held or note_id(n) in sustained or note_id(n) in organ_legato or note_id(n) in occurrence_guard or (n.track_index,n.channel) in controller_guard:continue
            nxt=next((x for x in onsets if x>n.onset),None)
            if nxt is None: continue
            ioi=nxt-n.onset
            if ioi<=1: continue
            cur=n.duration/float(ioi); target=clamp(center,wmin,wmax)
            ratio=cur+(target-cur)*(config.gate_strength*gate_scale)
            newdur=max(1,int(round(ioi*ratio))); newoff=n.onset+newdur
            # Safety cap: never create absurdly long tails.
            newoff=min(newoff,n.onset+ioi*2,track_ends.get(n.track_index,newoff))
            next_same=next((tick for tick in same_pitch_onsets[n.note] if tick>n.onset),None)
            if next_same is not None and n.off<=next_same:newoff=min(newoff,next_same)
            if newoff!=n.off:
                track_updates[n.track_index][n.off_index]=newoff
                reason='profile_gate:%s:%s:%s'%(policy.get('policy_family','UNKNOWN'),policy.get('gate_mode','PROFILE'),n.intent)
                report.changes.append(Change(n.track_index,n.off_index,'gate',n.off,newoff,reason,'',channel=n.channel,note=n.note,occurrence=n.occurrence,protected=n.protected)); n.off=newoff
    for ti,upd in track_updates.items():
        ev=absolute_track(mid.tracks[ti])
        for e in ev:
            if e[1] in upd:e[0]=upd[e[1]]
        mid.tracks[ti]=rebuild_track(ev)
