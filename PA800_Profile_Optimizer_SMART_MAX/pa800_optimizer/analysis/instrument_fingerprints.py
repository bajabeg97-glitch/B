"""Before/after fingerprint audit for the first specialized instrument families."""
from __future__ import annotations

from collections import defaultdict

from ..instruments.guards import EXPRESSIVE_FAMILIES,SUSTAINED_FAMILIES,exact_onset_groups,near_onset_groups,note_id
from ..instruments.policies import FAMILY_CUMULATIVE_VELOCITY_CAP,normalized_family

CONTROLLER_PRESERVE_FAMILIES=SUSTAINED_FAMILIES|EXPRESSIVE_FAMILIES|{'ORGAN'}


def snapshot_instrument_state(mid,notes,contexts):
    rows={};families={}
    for note in notes:
        key=note_id(note);ctx=contexts.get((note.track_index,note.channel));family=normalized_family(ctx.family if ctx else None)
        rows[key]={'onset':note.onset,'off':note.off,'velocity':note.velocity,'pitch':note.note};families[key]=family
    cc64=[];controllers=[]
    for track_index,track in enumerate(mid.tracks):
        tick=0
        for msg in track:
            tick+=int(getattr(msg,'time',0))
            if msg.type=='control_change' and msg.control==64:cc64.append((track_index,msg.channel,tick,msg.value))
            channel=getattr(msg,'channel',None);ctx=contexts.get((track_index,channel)) if channel is not None else None;family=normalized_family(ctx.family if ctx else None)
            if family not in CONTROLLER_PRESERVE_FAMILIES:continue
            if msg.type=='control_change' and msg.control not in (91,93):controllers.append((track_index,channel,tick,'cc',msg.control,msg.value))
            elif msg.type=='pitchwheel':controllers.append((track_index,channel,tick,'pitchwheel',msg.pitch))
            elif msg.type=='aftertouch':controllers.append((track_index,channel,tick,'aftertouch',msg.value))
            elif msg.type=='polytouch':controllers.append((track_index,channel,tick,'polytouch',msg.note,msg.value))
    return {'notes':rows,'families':families,'cc64':cc64,'controllers':controllers,'ticks_per_beat':mid.ticks_per_beat}


def _nearest_distance(value,anchors):
    return min((abs(value-anchor) for anchor in anchors),default=None)


def audit_instrument_fingerprints(before,mid,notes,contexts):
    after=snapshot_instrument_state(mid,notes,contexts);before_rows=before['notes'];after_rows=after['notes'];families=before['families'];tpb=max(1,int(before.get('ticks_per_beat',192)))
    common=set(before_rows)&set(after_rows);drum_before=[row['onset'] for key,row in before_rows.items() if families.get(key)=='DRUM_KIT'];drum_after=[row['onset'] for key,row in after_rows.items() if families.get(key)=='DRUM_KIT']
    velocity_budget_violations=[]
    for key in sorted(common):
        family=families.get(key,'UNKNOWN');cap=FAMILY_CUMULATIVE_VELOCITY_CAP.get(family,16);delta=abs(int(after_rows[key]['velocity'])-int(before_rows[key]['velocity']))
        if delta>cap:velocity_budget_violations.append({'note_id':list(key),'family':family,'before':before_rows[key]['velocity'],'after':after_rows[key]['velocity'],'delta':delta,'cap':cap})
    bass_total=0;bass_worsened=[]
    for key in sorted(common):
        if families.get(key)!='BASS':continue
        old=_nearest_distance(before_rows[key]['onset'],drum_before);new=_nearest_distance(after_rows[key]['onset'],drum_after)
        if old is None or new is None or old>tpb//4:continue
        bass_total+=1
        if new>old+1:bass_worsened.append({'note_id':list(key),'before_ticks':old,'after_ticks':new})
    by_context=defaultdict(list)
    for key,row in before_rows.items():by_context[(key[0],key[1],families.get(key))].append((key,row))
    guitar_groups=0;guitar_reversed=[];guitar_spread_drift=[];piano_chords=0;piano_desync=[];piano_spread_fail=[];sustain_chords=0;sustain_desync=[];sustain_shortened=[];organ_notes=0;organ_velocity_excess=[];organ_legato_lost=[]
    for (_track,_channel,family),pairs in by_context.items():
        proxy=[]
        for key,row in pairs:proxy.append(type('N',(),{'track_index':key[0],'channel':key[1],'note':key[2],'occurrence':key[3],**row})())
        if family=='GUITAR':
            for group in near_onset_groups(proxy,max(1,tpb//32)):
                if len({note.note for note in group})<2:continue
                keys=[note_id(note) for note in group if note_id(note) in common]
                if len(keys)<2:continue
                guitar_groups+=1
                for i,a in enumerate(keys):
                    for b in keys[i+1:]:
                        old_delta=before_rows[b]['onset']-before_rows[a]['onset'];new_delta=after_rows[b]['onset']-after_rows[a]['onset']
                        if old_delta and old_delta*new_delta<0:guitar_reversed.append([list(a),list(b)])
                old_spread=max(before_rows[key]['onset'] for key in keys)-min(before_rows[key]['onset'] for key in keys);new_spread=max(after_rows[key]['onset'] for key in keys)-min(after_rows[key]['onset'] for key in keys)
                if old_spread and abs(new_spread-old_spread)>max(2,old_spread*.25):guitar_spread_drift.append({'notes':[list(key) for key in keys],'before_ticks':old_spread,'after_ticks':new_spread})
        elif family=='PIANO':
            for group in exact_onset_groups(proxy):
                keys=[note_id(note) for note in group if note_id(note) in common]
                if len(keys)<2:continue
                piano_chords+=1
                if len({after_rows[key]['onset'] for key in keys})>1:piano_desync.append([list(key) for key in keys])
                old_range=max(before_rows[key]['velocity'] for key in keys)-min(before_rows[key]['velocity'] for key in keys);new_range=max(after_rows[key]['velocity'] for key in keys)-min(after_rows[key]['velocity'] for key in keys)
                if old_range and new_range+1e-9<.75*old_range:piano_spread_fail.append({'notes':[list(key) for key in keys],'before':old_range,'after':new_range})
        elif family in SUSTAINED_FAMILIES:
            for group in exact_onset_groups(proxy):
                keys=[note_id(note) for note in group if note_id(note) in common]
                if len(keys)<2:continue
                sustain_chords+=1
                if len({after_rows[key]['onset'] for key in keys})>1:sustain_desync.append([list(key) for key in keys])
            for key,row in pairs:
                before_duration=row['off']-row['onset'];after_duration=after_rows[key]['off']-after_rows[key]['onset']
                if key in common and before_duration>=tpb*.75 and after_duration<before_duration:sustain_shortened.append({'note_id':list(key),'before_duration':before_duration,'after_duration':after_duration,'before_off':row['off'],'after_off':after_rows[key]['off']})
        elif family=='ORGAN':
            ordered=sorted((key,row) for key,row in pairs if key in common)
            onsets=sorted({row['onset'] for _key,row in ordered})
            for key,row in ordered:
                organ_notes+=1;delta=abs(after_rows[key]['velocity']-row['velocity'])
                if delta>12:organ_velocity_excess.append({'note_id':list(key),'delta':delta})
                next_onset=next((value for value in onsets if value>row['onset']),None)
                if next_onset is not None and row['off']>=next_onset and after_rows[key]['off']<next_onset:organ_legato_lost.append({'note_id':list(key),'next_onset':next_onset,'after_off':after_rows[key]['off']})
    cc64_preserved=before.get('cc64',[])==after.get('cc64',[]);controllers_preserved=before.get('controllers',[])==after.get('controllers',[])
    checks={'cumulative_velocity_delta_bounded':not velocity_budget_violations,'bass_drum_lock_preserved':not bass_worsened,'guitar_direction_preserved':not guitar_reversed,'guitar_spread_preserved':not guitar_spread_drift,'piano_chord_sync_preserved':not piano_desync,'piano_chord_velocity_spread_retained':not piano_spread_fail,'piano_cc64_contour_preserved':cc64_preserved,'sustain_chord_sync_preserved':not sustain_desync,'sustain_tails_not_shortened':not sustain_shortened,'organ_velocity_limited':not organ_velocity_excess,'organ_legato_preserved':not organ_legato_lost,'expressive_controller_contours_preserved':controllers_preserved}
    return {'schema':'PA800_INSTRUMENT_FINGERPRINT_AUDIT_V2','checks':checks,'velocity_budget':{'notes_evaluated':len(common),'violation_count':len(velocity_budget_violations),'family_caps':dict(sorted(FAMILY_CUMULATIVE_VELOCITY_CAP.items())),'samples':velocity_budget_violations[:16]},'bass':{'locked_notes_evaluated':bass_total,'worsened_count':len(bass_worsened),'samples':bass_worsened[:16]},'guitar':{'strum_groups_evaluated':guitar_groups,'direction_reversal_count':len(guitar_reversed),'spread_drift_count':len(guitar_spread_drift),'direction_samples':guitar_reversed[:8],'spread_samples':guitar_spread_drift[:8]},'piano':{'chord_groups_evaluated':piano_chords,'desynchronized_count':len(piano_desync),'spread_failure_count':len(piano_spread_fail),'cc64_preserved':cc64_preserved,'desync_samples':piano_desync[:8],'spread_samples':piano_spread_fail[:8]},'sustain':{'chord_groups_evaluated':sustain_chords,'desynchronized_count':len(sustain_desync),'shortened_tail_count':len(sustain_shortened),'desync_samples':sustain_desync[:8],'tail_samples':sustain_shortened[:8]},'organ':{'notes_evaluated':organ_notes,'velocity_excess_count':len(organ_velocity_excess),'legato_lost_count':len(organ_legato_lost),'velocity_samples':organ_velocity_excess[:8],'legato_samples':organ_legato_lost[:8]},'expressive_controllers':{'preserved':controllers_preserved,'before_events':len(before.get('controllers',[])),'after_events':len(after.get('controllers',[]))},'pass':all(checks.values())}