"""Deterministic repair of high-confidence Standard MIDI File defects.

The doctor works on the already loaded ``MidiFile`` object.  It never launches
another optimizer, guesses musical notes, remaps sounds, or quantizes content.
Only structural defects with an unambiguous safe repair are changed.
"""
from __future__ import annotations

from collections import defaultdict,deque
import copy,hashlib,json
import mido
from .compatibility import analyze_timing_map


def canonical_midi_digest(mid):
    """Hash the complete logical MIDI event stream, independent of file bytes."""
    tracks=[]
    for track in mid.tracks:
        tick=0;events=[]
        for msg in track:
            tick+=int(msg.time)
            payload=msg.dict();payload.pop('time',None)
            events.append({'tick':tick,'message':payload})
        tracks.append(events)
    payload={'type':int(getattr(mid,'type',1)),'ticks_per_beat':int(getattr(mid,'ticks_per_beat',0)),'tracks':tracks}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),default=str).encode('utf-8')).hexdigest()


def verify_repair_replay(raw_mid,repaired_mid,expected_repairs=None,minimum_note_ticks=1):
    """Replay Doctor from the untouched input and require the identical result."""
    replay=copy.deepcopy(raw_mid);audit=repair_midi(replay,minimum_note_ticks=minimum_note_ticks)
    expected=list(expected_repairs or [])
    actual=list(audit.get('repairs') or [])
    expected_hash=canonical_midi_digest(repaired_mid);actual_hash=canonical_midi_digest(replay)
    return {'schema':'PA800_DOCTOR_CANONICAL_REPLAY_V1','pass':bool(audit.get('pass')) and actual_hash==expected_hash and (not expected or actual==expected),'expected_digest':expected_hash,'replay_digest':actual_hash,'expected_repair_count':len(expected),'replay_repair_count':len(actual),'repair_list_match':not expected or actual==expected}



def repair_midi_transaction(raw_mid, minimum_note_ticks=1):
    """Run Doctor on an isolated copy and commit only a replay-verifiable result."""
    candidate=copy.deepcopy(raw_mid)
    audit=repair_midi(candidate,minimum_note_ticks=minimum_note_ticks)
    replay=verify_repair_replay(raw_mid,candidate,audit.get('repairs'),minimum_note_ticks=minimum_note_ticks)
    audit['canonical_replay']=replay
    audit['transaction']={
        'schema':'PA800_DOCTOR_TRANSACTION_V1',
        'production_midi_mutated_during_proposal':False,
        'candidate_digest':canonical_midi_digest(candidate),
        'source_digest':canonical_midi_digest(raw_mid),
        'commit_authorized':bool(audit.get('pass')) and bool(replay.get('pass')),
    }
    return candidate,audit

def _absolute(track):
    tick=0;rows=[]
    for seq,msg in enumerate(track):
        tick+=int(msg.time);rows.append({'tick':tick,'seq':seq,'msg':msg,'drop':False})
    return rows,tick


def scan_midi_health(mid):
    totals=defaultdict(int);tracks=[]
    invalid_resolution=int(getattr(mid,'ticks_per_beat',0)==0)
    for ti,track in enumerate(mid.tracks):
        rows,end_tick=_absolute(track);active=defaultdict(deque);sustain={};eot=[]
        row_counts=defaultdict(int)
        for row in list(rows):
            msg=row['msg'];tick=row['tick'];ch=getattr(msg,'channel',None)
            if msg.type=='end_of_track':eot.append(row);continue
            if msg.type=='set_tempo' and int(getattr(msg,'tempo',0))<=0:row_counts['invalid_tempo']+=1
            if msg.type=='time_signature':
                numerator=int(getattr(msg,'numerator',0));denominator=int(getattr(msg,'denominator',0))
                if numerator<=0 or denominator<=0 or denominator&(denominator-1):row_counts['invalid_time_signature']+=1
            if msg.type=='note_on' and msg.velocity>0:
                active[(ch,msg.note)].append(tick)
            elif msg.type in ('note_off','note_on') and (msg.type=='note_off' or msg.velocity==0):
                q=active[(ch,msg.note)]
                if not q:row_counts['orphan_note_off']+=1
                else:
                    onset=q.popleft()
                    if tick<=onset:row_counts['zero_duration_note']+=1
            elif msg.type=='control_change' and msg.control==64:
                sustain[ch]=msg.value
            elif msg.type=='control_change' and msg.control in (120,123):
                row_counts['channel_mode_note_terminations']+=sum(len(q) for (ach,_),q in active.items() if ach==ch)
                for key in [key for key in active if key[0]==ch]:active[key].clear()
        row_counts['dangling_note_on']=sum(len(q) for q in active.values())
        row_counts['stuck_sustain']=sum(1 for value in sustain.values() if value>=64)
        row_counts['missing_end_of_track']=int(not eot)
        row_counts['duplicate_end_of_track']=max(0,len(eot)-1)
        if eot:
            first=eot[0]['seq'];row_counts['events_after_end_of_track']=sum(1 for row in rows if row['seq']>first and row['msg'].type!='end_of_track')
        for key,value in row_counts.items():totals[key]+=value
        tracks.append({'track':ti,'end_tick':end_tick,**dict(row_counts)})
    # Same-tick Note-On/Off is legal and commonly used by one-shot Drum Kits.
    # Record it as evidence, but do not classify or repair it without context.
    timing_map=analyze_timing_map(mid);totals['tempo_map_conflicts']=len(timing_map['tempo']['conflicts']);totals['meter_map_conflicts']=len(timing_map['meter']['conflicts'])
    critical=('orphan_note_off','dangling_note_on','stuck_sustain','missing_end_of_track','duplicate_end_of_track','events_after_end_of_track','invalid_tempo','invalid_time_signature','tempo_map_conflicts','meter_map_conflicts')
    result={key:int(totals.get(key,0)) for key in critical}
    result['zero_duration_note']=int(totals.get('zero_duration_note',0))
    result['channel_mode_note_terminations']=int(totals.get('channel_mode_note_terminations',0))
    result['invalid_ticks_per_beat']=invalid_resolution
    result['tracks']=tracks;result['timing_map']=timing_map;result['pass']=not any(result[key] for key in critical)
    result['pass']=result['pass'] and not invalid_resolution
    return result


def repair_midi(mid,minimum_note_ticks=1):
    """Repair safe structural MIDI defects in place and return an audit."""
    before=scan_midi_health(mid);repairs=[];plan=[]
    for key,value in before.items():
        if isinstance(value,int) and value and key not in ('zero_duration_note','channel_mode_note_terminations','invalid_ticks_per_beat','tempo_map_conflicts','meter_map_conflicts'):plan.append({'kind':'REPAIR_'+key.upper(),'count':value})
    if before.get('invalid_ticks_per_beat'):plan.append({'kind':'REPLACE_ZERO_TICKS_PER_BEAT','count':1})
    if before.get('channel_mode_note_terminations'):plan.append({'kind':'MATERIALIZE_CHANNEL_MODE_NOTE_OFFS','count':before['channel_mode_note_terminations']})
    # Within one track, multiple meter events at the same absolute tick are
    # executed in event order without any elapsed musical time.  Therefore all
    # but the final event are immediately shadowed and can be removed without
    # guessing a meter.  Cross-track conflicts remain unrecoverable because
    # SMF does not define a global ordering between simultaneous tracks.
    shadowed_meter={}
    for conflict in before.get('timing_map',{}).get('meter',{}).get('conflicts',[]):
        events=list(conflict.get('events') or []);tracks={int(row['track']) for row in events}
        if len(events)<2 or len(tracks)!=1:continue
        winner=max(events,key=lambda row:int(row['event_index']))
        for row in events:
            if row is winner:continue
            shadowed_meter[(int(row['track']),int(row['event_index']))]={'retained_event_index':int(winner['event_index']),'retained_meter':list(winner['value'])}
    if shadowed_meter:plan.append({'kind':'COLLAPSE_SHADOWED_SAME_TICK_METER','count':len(shadowed_meter)})
    if getattr(mid,'ticks_per_beat',0)==0:
        mid.ticks_per_beat=480
        repairs.append({'track':None,'channel':None,'tick':None,'kind':'REPLACE_ZERO_TICKS_PER_BEAT','new_value':480})
    minimum_note_ticks=max(1,int(minimum_note_ticks))
    for ti,track in enumerate(mid.tracks):
        rows,original_end=_absolute(track);active=defaultdict(deque);sustain={};eot_rows=[];current_tempo=500000;current_meter=(4,4,24,8)
        next_seq=len(rows)
        for row in list(rows):
            msg=row['msg'];tick=row['tick'];ch=getattr(msg,'channel',None)
            if msg.type=='end_of_track':
                eot_rows.append(row);row['drop']=True;continue
            shadow=shadowed_meter.get((ti,int(row['seq'])))
            if msg.type=='time_signature' and shadow is not None:
                row['drop']=True
                repairs.append({'track':ti,'channel':None,'tick':tick,'kind':'REMOVE_SHADOWED_TIME_SIGNATURE','old_meter':[int(msg.numerator),int(msg.denominator),int(getattr(msg,'clocks_per_click',24)),int(getattr(msg,'notated_32nd_notes_per_beat',8))],**shadow})
                continue
            if msg.type=='set_tempo' and int(getattr(msg,'tempo',0))<=0:
                row['msg']=msg.copy(tempo=current_tempo);msg=row['msg']
                repairs.append({'track':ti,'channel':None,'tick':tick,'kind':'REPLACE_INVALID_TEMPO','new_tempo':current_tempo,'basis':'previous_valid_or_smf_default'})
            elif msg.type=='set_tempo':current_tempo=int(msg.tempo)
            if msg.type=='time_signature':
                numerator=int(getattr(msg,'numerator',0));denominator=int(getattr(msg,'denominator',0))
                if numerator<=0 or denominator<=0 or denominator&(denominator-1):
                    row['msg']=msg.copy(numerator=current_meter[0],denominator=current_meter[1],clocks_per_click=current_meter[2],notated_32nd_notes_per_beat=current_meter[3]);msg=row['msg']
                    repairs.append({'track':ti,'channel':None,'tick':tick,'kind':'REPLACE_INVALID_TIME_SIGNATURE','new_meter':list(current_meter),'basis':'previous_valid_or_smf_default'})
                else:current_meter=(numerator,denominator,int(getattr(msg,'clocks_per_click',24)),int(getattr(msg,'notated_32nd_notes_per_beat',8)))
            if msg.type=='note_on' and msg.velocity>0:
                active[(ch,msg.note)].append(row);continue
            if msg.type in ('note_off','note_on') and (msg.type=='note_off' or msg.velocity==0):
                q=active[(ch,msg.note)]
                if not q:
                    row['drop']=True
                    repairs.append({'track':ti,'channel':None if ch is None else ch+1,'tick':tick,'kind':'REMOVE_ORPHAN_NOTE_OFF','note':msg.note})
                    continue
                onset=q.popleft()['tick']
                # Preserve legal same-tick Note-Off. Context-aware melodic repair
                # belongs to a later phase; Drum one-shots must remain untouched.
                continue
            if msg.type=='control_change' and msg.control==64:sustain[ch]=msg.value
            elif msg.type=='control_change' and msg.control in (120,123):
                for (ach,note),queue in sorted(active.items()):
                    if ach!=ch:continue
                    while queue:
                        onset=queue.popleft()['tick'];rows.append({'tick':tick,'seq':row['seq']-.1,'msg':mido.Message('note_off',channel=ch,note=note,velocity=0,time=0),'drop':False})
                        repairs.append({'track':ti,'channel':ch+1,'tick':tick,'kind':'MATERIALIZE_CHANNEL_MODE_NOTE_OFF','note':note,'onset_tick':onset,'controller':msg.control})

        final_tick=max([original_end]+[int(row['tick']) for row in rows if not row['drop']])
        for (ch,note),queue in sorted(active.items()):
            while queue:
                onset=queue.popleft()['tick'];off_tick=max(original_end,onset+minimum_note_ticks);final_tick=max(final_tick,off_tick)
                rows.append({'tick':off_tick,'seq':next_seq,'msg':mido.Message('note_off',channel=ch,note=note,velocity=0,time=0),'drop':False});next_seq+=1
                repairs.append({'track':ti,'channel':ch+1,'tick':off_tick,'kind':'ADD_MISSING_NOTE_OFF','note':note,'onset_tick':onset})
        for ch,value in sorted(sustain.items()):
            if value>=64:
                rows.append({'tick':final_tick,'seq':next_seq,'msg':mido.Message('control_change',channel=ch,control=64,value=0,time=0),'drop':False});next_seq+=1
                repairs.append({'track':ti,'channel':ch+1,'tick':final_tick,'kind':'RELEASE_STUCK_SUSTAIN','old_value':value})

        if not eot_rows:
            repairs.append({'track':ti,'channel':None,'tick':final_tick,'kind':'ADD_END_OF_TRACK'})
        elif len(eot_rows)>1:
            repairs.append({'track':ti,'channel':None,'tick':final_tick,'kind':'COLLAPSE_DUPLICATE_END_OF_TRACK','removed':len(eot_rows)-1})
        if eot_rows and any(row['seq']>eot_rows[0]['seq'] and row['msg'].type!='end_of_track' for row in rows):
            repairs.append({'track':ti,'channel':None,'tick':final_tick,'kind':'MOVE_END_OF_TRACK_TO_END'})
        rows.append({'tick':final_tick,'seq':next_seq+1,'msg':mido.MetaMessage('end_of_track',time=0),'drop':False})
        kept=[row for row in rows if not row['drop']]
        kept.sort(key=lambda row:(max(0,int(row['tick'])),row['seq']))
        rebuilt=mido.MidiTrack();prev=0
        for row in kept:
            tick=max(prev,int(row['tick']));rebuilt.append(row['msg'].copy(time=tick-prev));prev=tick
        mid.tracks[ti]=rebuilt
    after=scan_midi_health(mid)
    unrecoverable=[]
    if after.get('tempo_map_conflicts'):unrecoverable.append('conflicting_tempo_events_at_same_tick')
    if after.get('meter_map_conflicts'):unrecoverable.append('conflicting_meter_events_at_same_tick')
    return {'enabled':True,'before':before,'repair_plan':plan,'after':after,'repairs':repairs,'repair_count':len(repairs),'unrecoverable':unrecoverable,'pass':after['pass']}