"""Instrument, controller, section and phrase-aware velocity calibration."""
from __future__ import annotations

from collections import defaultdict
import json,math,statistics
from pathlib import Path

from ..models import Change
from ..instruments.policies import policy_for,profile_evidence_allows_mutation
from ..instruments.guards import retain_group_spread
from ..utils import clamp

FAMILY_MAX_DELTA={'PIANO':28,'BASS':20,'GUITAR':24,'BRASS':14,'REED':12,'PIPE':12,'HARMONICA':10,'ACCORDION':10,'SYNTH_LEAD':12,'STRINGS':12,'ENSEMBLE':12,'SYNTH_PAD':10,'CHOIR_VOICE':10,'ORGAN':4,'DRUM_KIT':14,'PERCUSSION':14,'PERCUSSIVE':14}
SECTION_FACTOR={'Variation 1':.97,'Variation 2':.99,'Variation 3':1.01,'Variation 4':1.03,'Fill 1':1.02,'Fill 2':1.02,'Break':.98,'Intro 1':.97,'Intro 2':.98,'Intro 3':1.0,'Ending 1':.98,'Ending 2':.99,'Ending 3':1.0}


def _percentile(values,q):
    if not values:return 0.0
    vals=sorted(values);pos=(len(vals)-1)*q;lo=int(pos);hi=min(len(vals)-1,lo+1);f=pos-lo
    return vals[lo]*(1-f)+vals[hi]*f


def _iqr(values):return _percentile(values,.75)-_percentile(values,.25)


def _spec(profile,velocity):
    pv=(profile or {}).get('velocity') or {};center=float(pv.get('ideal_center',velocity) or velocity)
    if center<=0:return None
    lo=int(max(1,pv.get('p05',pv.get('working_min',1))));hi=int(min(127,pv.get('p95',pv.get('working_max',127))))
    return center,lo,hi


def _controller_state(track,channel):
    volume=100;expression=127;out={}
    for index,msg in enumerate(track):
        if getattr(msg,'channel',None)!=channel:continue
        if msg.type=='control_change' and msg.control==7:volume=msg.value
        elif msg.type=='control_change' and msg.control==11:expression=msg.value
        elif msg.type=='note_on' and msg.velocity>0:
            scale=math.sqrt(max(.01,(volume/100.0)*(expression/127.0)))
            out[index]={'cc7':volume,'cc11':expression,'scale':scale}
    return out


def _load_calibration(path):
    if not path:return {},None
    p=Path(path)
    try:
        data=json.loads(p.read_text(encoding='utf-8'));return data if isinstance(data,dict) else {},str(p)
    except Exception:return {},str(p)


def _calibration_offset(data,ctx):
    address='.'.join(str(x) for x in ctx.identity.address())
    addresses=data.get('addresses',{}) if isinstance(data,dict) else {};families=data.get('families',{}) if isinstance(data,dict) else {}
    value=addresses.get(address,families.get(ctx.family,0))
    try:return float(clamp(float(value),-24,24))
    except Exception:return 0.0


def _phrase_factor(note,arr,tpq):
    if len(arr)<8:return 1.0
    beat=max(1,tpq);start=min(n.onset for n in arr);end=max(n.off for n in arr);span=max(beat,end-start)
    position=(note.onset-start)/span
    if position<.08:return 1.015
    if position>.92:return .99
    return 1.0


def normalize_velocity(mid,notes,contexts,profiles,registry,config,report):
    if not config.enable_velocity or not config.enable_velocity_conductor:
        report.velocity_conductor={'enabled':False,'contexts':[],'pass':True};return
    calibration,calibration_source=_load_calibration(config.hardware_calibration_path)
    groups=defaultdict(list)
    for note in notes:
        if not note.protected:groups[(note.track_index,note.channel)].append(note)
    rows=[];global_before=[];global_after=[];total_changes=0
    for key,arr in groups.items():
        ctx=contexts.get(key);parent=profiles.get(key);basis='EXACT_SOUND_PROFILE'
        policy=policy_for(ctx.family) if ctx else policy_for('UNKNOWN')
        if not ctx or not policy.get('velocity',False):continue
        if ctx and not parent and not getattr(config,'velocity_factory_data_only',True) and not policy.get('exact_only') and hasattr(registry,'velocity_family_profile'):
            parent=registry.velocity_family_profile(ctx.family,ctx.role);basis='FACTORY_FAMILY_AGGREGATE'
        if ctx.identity.conflict or not parent or not profile_evidence_allows_mutation(policy,parent) or len(arr)<4:continue
        controller=_controller_state(mid.tracks[key[0]],key[1]);values=[];kit_hits=0
        for note in arr:
            prof=parent
            if ctx.family=='DRUM_KIT' or ctx.role in ('DRUM','PERC'):
                candidate=registry.resolve_drum_key(ctx.identity.msb,ctx.identity.lsb,ctx.identity.program,note.note)
                support=(candidate or {}).get('support',{})
                if candidate and int(support.get('hits',0))>=config.drum_key_min_hits and int(support.get('styles',0))>=config.drum_key_min_styles:
                    prof=candidate;kit_hits+=1
            spec=_spec(prof,note.velocity)
            if spec:values.append((note,spec,controller.get(note.on_index,{'cc7':100,'cc11':127,'scale':1.0})))
        if len(values)<4:continue
        raw_ratios=[note.velocity/spec[0] for note,spec,_ in values]
        energy_ratios=[(note.velocity/spec[0])*state['scale'] for note,spec,state in values]
        before=float(statistics.median(raw_ratios));energy_before=float(statistics.median(energy_ratios));controller_scale=float(statistics.median(state['scale'] for _,_,state in values))
        desired=before+(1.0-before)*float(config.velocity_conductor_strength)
        if config.mode!='preserve':desired=float(clamp(desired,0.94,1.06))
        desired*=SECTION_FACTOR.get(ctx.element,1.0)
        desired*=float(clamp(1.0+(1.0-controller_scale)*.25,.90,1.15))
        calibration_offset=_calibration_offset(calibration,ctx)
        desired+=calibration_offset/max(1.0,statistics.median(spec[0] for _,spec,_ in values))
        shift=desired-before;track=mid.tracks[key[0]];family_cap=min(config.velocity_conductor_max_delta,FAMILY_MAX_DELTA.get(ctx.family,config.velocity_conductor_max_delta));proposed=[]
        for note,(center,lo,hi),_state in values:
            local_shift=shift*_phrase_factor(note,arr,mid.ticks_per_beat);raw=center*((note.velocity/center)+local_shift)
            profiled=float(clamp(raw,lo,hi));capped=float(clamp(profiled,note.velocity-family_cap,note.velocity+family_cap));proposed.append(int(round(clamp(capped,1,127))))
        original=[note.velocity for note,_,_ in values];orig_iqr=_iqr(original);new_iqr=_iqr(proposed);retention=1.0 if orig_iqr<=0 else new_iqr/orig_iqr
        if retention<float(config.velocity_min_iqr_retention) and orig_iqr>0:
            target=float(config.velocity_min_iqr_retention);low_alpha=0.0;high_alpha=1.0;best=list(original)
            for _ in range(16):
                alpha=(low_alpha+high_alpha)/2.0;candidate=[int(round(old+(new-old)*alpha)) for old,new in zip(original,proposed)];candidate_retention=_iqr(candidate)/orig_iqr
                if candidate_retention>=target:best=candidate;low_alpha=alpha
                else:high_alpha=alpha
            proposed=best;new_iqr=_iqr(proposed);retention=new_iqr/orig_iqr
        if str(ctx.family).upper()=='PIANO':
            proposed=retain_group_spread([item[0] for item in values],proposed,.75)
            new_iqr=_iqr(proposed);retention=1.0 if orig_iqr<=0 else new_iqr/orig_iqr
        changed=0
        for (note,_specification,_state),new in zip(values,proposed):
            if new!=note.velocity:
                old=note.velocity;track[note.on_index]=track[note.on_index].copy(velocity=new);note.velocity=new;changed+=1;total_changes+=1
                report.changes.append(Change(key[0],note.on_index,'velocity_conductor',old,new,'instrument_energy_center',ctx.identity.name or ctx.family,channel=note.channel,note=note.note,occurrence=note.occurrence,protected=note.protected))
        after=float(statistics.median(note.velocity/spec[0] for note,spec,_ in values));energy_after=float(statistics.median((note.velocity/spec[0])*state['scale'] for note,spec,state in values))
        global_before.extend(raw_ratios);global_after.extend(note.velocity/spec[0] for note,spec,_ in values)
        evidence='E3' if calibration_offset else 'E2' if basis=='EXACT_SOUND_PROFILE' else 'E1'
        rows.append({'track':key[0],'channel':key[1]+1,'sound':ctx.identity.name,'family':ctx.family,'role':ctx.role,'element':ctx.element,'profile_basis':basis,'evidence_level':evidence,'notes':len(values),'kit_key_supported_notes':kit_hits,'cc7_median':statistics.median(state['cc7'] for _,_,state in values),'cc11_median':statistics.median(state['cc11'] for _,_,state in values),'controller_energy_scale':round(controller_scale,4),'effective_energy_before':round(energy_before,4),'effective_energy_after':round(energy_after,4),'normalized_median_before':round(before,4),'normalized_median_target':round(desired,4),'normalized_median_after':round(after,4),'iqr_before':round(orig_iqr,3),'iqr_after':round(new_iqr,3),'iqr_retention':round(retention,4),'family_delta_cap':family_cap,'hardware_calibration_offset':calibration_offset,'changes':changed,'status':'NORMAL' if 0.82<=after<=1.18 and retention+1e-6>=float(config.velocity_min_iqr_retention) else 'LIMITED_BY_PROFILE_OR_DYNAMIC_GUARD'})
    gb=statistics.median(global_before) if global_before else None;ga=statistics.median(global_after) if global_after else None
    report.velocity_conductor={'enabled':True,'method':'exact Factory profile center + CC7/CC11 effective energy + section/phrase contour + family limiter','factory_data_only':bool(getattr(config,'velocity_factory_data_only',True)),'normal_corridor':[0.82,1.18],'minimum_iqr_retention':config.velocity_min_iqr_retention,'hardware_calibration_source':calibration_source,'controllers_rewritten':False,'contexts':rows,'processed_contexts':len(rows),'changes':total_changes,'global_normalized_median_before':None if gb is None else round(gb,4),'global_normalized_median_after':None if ga is None else round(ga,4),'pass':all(row['status']=='NORMAL' for row in rows)}