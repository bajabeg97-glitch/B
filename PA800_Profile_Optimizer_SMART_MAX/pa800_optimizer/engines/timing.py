from collections import defaultdict
from pathlib import Path
from ..core.midi_io import absolute_track, rebuild_track
from ..utils import stable_seed, deterministic_gauss, clamp
from ..models import Change
from ..instruments.policies import policy_for,profile_evidence_allows_mutation
from ..instruments.guards import ambiguous_occurrence_note_ids,exact_onset_groups,expressive_controller_channels,near_onset_groups,note_id,organ_legato_note_ids,sustained_timing_guard_ids
from ..neural.self_supervised_encoder import _predict_masked_array,load_encoder_model,encoder_runtime_admission
from ..neural.corpus_router import route_authority

_TRAINED_MODEL_CACHE={}


def _trill_groups(notes,max_gap):
    """Return trill, mordent and rapid-repeat runs for bounded spacing repair."""
    arr=sorted(notes,key=lambda note:(note.onset,note.note,note.occurrence));groups=[];start=None
    for index in range(2,len(arr)):
        a,b,c=arr[index-2:index+1];alternating=a.note==c.note and 1<=abs(b.note-a.note)<=2
        close=(b.onset-a.onset)<=max_gap and (c.onset-b.onset)<=max_gap
        if alternating and close:
            if start is None:start=index-2
        elif start is not None:
            if index-start>=4:groups.append(arr[start:index])
            start=None
    if start is not None and len(arr)-start>=4:groups.append(arr[start:])
    # Three-note ABA mordents/turns and rapid repeated-note ornaments are
    # valid solo ornaments too; never change their pitches or note count.
    for index in range(len(arr)-2):
        trio=arr[index:index+3];close=all(b.onset-a.onset<=max_gap for a,b in zip(trio,trio[1:]));mordent=trio[0].note==trio[2].note and 1<=abs(trio[1].note-trio[0].note)<=2;repeat=len({note.note for note in trio})==1
        if close and (mordent or repeat) and not any(set(note.on_index for note in trio)<=set(note.on_index for note in group) for group in groups):groups.append(trio)
    return sorted(groups,key=lambda group:(group[0].onset,len(group)))


def _factory_gold_route(ctx):
    family=str(getattr(ctx,'family','UNKNOWN') or 'UNKNOWN').upper();role=str(getattr(ctx,'role','') or '').upper();element=str(getattr(ctx,'element','') or '').upper()
    if family in ('DRUM_KIT','PERCUSSIVE') or role in ('DRUM','PERC'):head='FILL_CONTENT' if ('FILL' in element or 'BREAK' in element) else 'DRUM_PATTERN'
    elif family=='BASS' or role=='BASS':head='BASS_PATTERN'
    elif family=='GUITAR':head='POWERCHORD_RIFF' if any(word in role for word in ('POWER','RIFF')) else 'GUITAR_STRUM'
    elif family=='BRASS':head='BRASS_PATTERN'
    elif family in ('STRINGS','ENSEMBLE','SYNTH_PAD'):head='STRINGS_PAD_PATTERN'
    elif family in ('REED','PIPE','ACCORDION_REED','SYNTH_LEAD','ETHNIC') or any(word in role for word in ('SOLO','LEAD','COUNTER')):head='SOLO_PHRASE'
    else:head='NO_EVIDENCE'
    route=route_authority(head)
    if route.get('status')!='ROUTED':return {'head':head,'selected_source':'PROFILE_GUARD','selected_weight':0.0,'correction_scale':1.0,**route}
    factory=float(route.get('factory',0));gold=float(route.get('gold',0));selected='FACTORY' if factory>=gold else 'GOLD';weight=max(factory,gold)
    return {**route,'head':head,'selected_source':selected,'selected_weight':weight,'correction_scale':round(.75+.5*weight,4)}


def _trained_rhythm_shifts(mid,notes,contexts,model_path,factory_gold_max=False):
    """Return bounded onset/gate proposals; velocity and Voice data are unused."""
    path=Path(model_path).resolve()
    try:
        stat=path.stat();cache_key=(str(path),stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)
    except FileNotFoundError:cache_key=None
    model=_TRAINED_MODEL_CACHE.get(cache_key) if cache_key is not None else None
    if model is None:
        model=load_encoder_model(path,require_accepted=True)
        if cache_key is not None:
            if len(_TRAINED_MODEL_CACHE)>=4:_TRAINED_MODEL_CACHE.clear()
            _TRAINED_MODEL_CACHE[cache_key]=model
    admission=encoder_runtime_admission(model)
    if not admission['proposal_allowed']:
        return {},{},{},{},{'schema':'PA800_TRAINED_MUSIC_APPLICATION_V3','model_digest':model['model_digest'],'model_acceptance':model.get('acceptance'),'runtime_admission':admission,'factory_gold_max':bool(factory_gold_max),'authority_selection':{},'feature_heads':{},'timing_proposed_notes':0,'duration_proposed_notes':0,'velocity_features_applied':0,'pitch_features_applied':0,'voice_settings_applied':0,'sound_kit_features_applied':0,'articulation_features_applied':0,'fx_features_applied':0,'expression_features_applied':0,'velocity_policy':'PROFILE_ONLY','explicit_user_authority':True,'fallback':'FACTORY_GOLD_DETERMINISTIC','authority_granted':False}
    tpb=max(1,int(mid.ticks_per_beat));simultaneous=defaultdict(list)
    for note in notes:simultaneous[(note.track_index,note.channel,note.onset)].append(note)
    ordered=sorted(notes,key=lambda row:(row.track_index,row.channel,row.onset,row.note,row.occurrence));tokens=[]
    voice_pitches={key:sorted(row.note for row in group) for key,group in simultaneous.items()}
    for note in ordered:
        ctx=contexts.get((note.track_index,note.channel));group_key=(note.track_index,note.channel,note.onset);group=simultaneous[group_key]
        tokens.append({'track':note.track_index,'channel':note.channel,'pitch':note.note,'velocity':note.velocity,'onset':note.onset,'off':note.off,'duration':note.duration,'occurrence':note.occurrence,'position_in_beat':note.onset%tpb,'position_in_bar':note.onset%(tpb*4),'bar_ticks':tpb*4,'bar':note.onset//(tpb*4),'simultaneous_group_size':len(group),'voice_index':voice_pitches[group_key].index(note.note),'protected':note.protected,'family':getattr(ctx,'family','UNKNOWN'),'role':getattr(ctx,'role','UNKNOWN'),'element':getattr(ctx,'element',None),'cv':getattr(ctx,'cv',None)})
    prediction_names,predictions=_predict_masked_array({'midi':{'ticks_per_beat':tpb},'note_tokens':tokens},model,('onset_delta_beats','duration_beats'));onset_column=prediction_names.index('onset_delta_beats');duration_column=prediction_names.index('duration_beats');previous={};raw={};reasons={};gate={};gate_reasons={};step_cap=max(1,tpb//32)
    authority_counts=defaultdict(int);head_counts=defaultdict(int)
    for note,token,prediction in zip(ordered,tokens,predictions):
        key=(note.track_index,note.channel);prior=previous.get(key);previous[key]=note
        if prior is None or note.protected or token['simultaneous_group_size']>1:continue
        # R11: neural inference never owns the final timing/gate authority.
        # All admitted proposals are routed through Factory/Gold evidence; the
        # mid-confidence advisor band is additionally attenuated.
        route=_factory_gold_route(contexts.get(key))
        scale=float(route['correction_scale'])
        if admission['mode']=='ADVISOR_ONLY':scale*=0.50
        authority_counts[route['selected_source']]+=1;head_counts[route['head']]+=1
        actual=max(0,note.onset-prior.onset);predicted=float(clamp(prediction[onset_column],0.0,1.0))*8.0*tpb
        correction=int(round(clamp((predicted-actual)*.35*scale,-step_cap,step_cap)))
        if correction:raw[note_id(note)]=correction;reasons[note_id(note)]='explicit_trained_rhythm_model'
        predicted_duration=float(clamp(prediction[duration_column],0.0,1.0))*8.0*tpb
        gate_delta=int(round(clamp((predicted_duration-note.duration)*.25*scale,-step_cap,step_cap)))
        if gate_delta:gate[note_id(note)]=gate_delta;gate_reasons[note_id(note)]='explicit_trained_note_duration'
    grouped=defaultdict(list)
    for note in ordered:grouped[(note.track_index,note.channel)].append(note)
    total_cap=max(1,tpb//8)
    for arr in grouped.values():
        for group in _trill_groups(arr,max(1,tpb//2)):
            cumulative=0
            for note in group:
                cumulative=int(clamp(cumulative+raw.get(note_id(note),0),-total_cap,total_cap))
                if cumulative:raw[note_id(note)]=cumulative;reasons[note_id(note)]='explicit_trained_trill_spacing'
    return raw,reasons,gate,gate_reasons,{'schema':'PA800_TRAINED_MUSIC_APPLICATION_V3','model_digest':model['model_digest'],'model_acceptance':model['acceptance'],'runtime_admission':admission,'factory_gold_max':bool(factory_gold_max),'authority_selection':dict(sorted(authority_counts.items())),'feature_heads':dict(sorted(head_counts.items())),'timing_proposed_notes':len(raw),'duration_proposed_notes':len(gate),'velocity_features_applied':0,'pitch_features_applied':0,'voice_settings_applied':0,'sound_kit_features_applied':0,'articulation_features_applied':0,'fx_features_applied':0,'expression_features_applied':0,'velocity_policy':'PROFILE_ONLY','explicit_user_authority':True,'authority_granted':False}

def optimize_timing(mid, notes, contexts, profiles, registry, config, report):
    if not config.enable_timing or config.timing_strength<=0:return
    active=[];track_events={};track_ends={}
    for ti in {note.track_index for note in notes}:
        track_events[ti]=absolute_track(mid.tracks[ti]);track_ends[ti]=max((event[0] for event in track_events[ti]),default=0)
    sustain_guard=sustained_timing_guard_ids(notes,contexts);organ_guard=organ_legato_note_ids(notes,contexts);occurrence_guard=ambiguous_occurrence_note_ids(notes);controller_guard=expressive_controller_channels(mid,contexts);planned={};planned_reason={};trained={};trained_reason={};trained_gate={};trained_gate_reason={}
    if getattr(config,'apply_trained_rhythm_model',False):
        if not getattr(config,'trained_rhythm_model_path',None):raise ValueError('Trained rhythm model path is required')
        trained,trained_reason,trained_gate,trained_gate_reason,summary=_trained_rhythm_shifts(mid,notes,contexts,config.trained_rhythm_model_path,getattr(config,'factory_gold_max',False));report.workstation['trained_rhythm_application']=summary
    for n in notes:
        if n.protected:continue
        ctx=contexts.get((n.track_index,n.channel));p=profiles.get((n.track_index,n.channel))
        if not ctx:continue
        policy=policy_for(ctx.family)
        if not p or not ctx or not policy.get('timing',False) or not profile_evidence_allows_mutation(policy,p):continue
        family_scale=float(policy.get('timing_scale',1.0));family=policy.get('policy_family','UNKNOWN');mode=policy.get('timing_mode','PROFILE')
        if family_scale<=0:continue
        if getattr(config,'trained_rhythm_only',False):
            planned[note_id(n)]=int(round(trained.get(note_id(n),0)*family_scale));planned_reason[note_id(n)]=trained_reason.get(note_id(n),'explicit_trained_rhythm_model')+':'+family+':'+mode;active.append((n,ctx));continue
        dp=registry.resolve_drum_key(ctx.identity.msb,ctx.identity.lsb,ctx.identity.program,n.note) if (ctx.family=='DRUM_KIT' or ctx.role in ('DRUM','PERC')) else None
        if dp:tr=dp.get('timing_residual',{});key='24' if '24' in tr else next(iter(tr),None);z=tr.get(key,{}) if key else {}
        else:tr=p.get('timing_residual_ticks',{});key='grid_1_32_24' if 'grid_1_32_24' in tr else next(iter(tr),None);z=tr.get(key,{}) if key else {}
        wlo=float(z.get('working_min',-2));whi=float(z.get('working_max',2));scale=mid.ticks_per_beat/192.0;lo=wlo*scale;hi=whi*scale;effective_strength=config.timing_strength*family_scale;sigma=max(.4,min(3.5,(hi-lo)/3.0))*effective_strength
        off=deterministic_gauss(stable_seed(config.seed,'timing',n.track_index,n.channel,n.onset,n.note,n.on_index,n.intent),0,sigma);off=clamp(off,lo*effective_strength,hi*effective_strength);shift=int(round(off));shift=max(-n.onset,min(shift,track_ends[n.track_index]-n.off))
        shift+=int(round(trained.get(note_id(n),0)*family_scale));shift=max(-n.onset,min(shift,track_ends[n.track_index]-n.off));planned[note_id(n)]=shift;planned_reason[note_id(n)]=trained_reason.get(note_id(n),'profile_residual_guarded')+':'+family+':'+mode;active.append((n,ctx))
    raw_planned=dict(planned)
    for key in sustain_guard|organ_guard|occurrence_guard:
        if key in planned:planned[key]=0
        if key in trained_gate:trained_gate[key]=0
    by_context=defaultdict(list)
    for note,_ctx in active:by_context[(note.track_index,note.channel)].append(note)
    for context_key,arr in by_context.items():
        ctx=contexts.get(context_key);family=policy_for(ctx.family if ctx else 'UNKNOWN').get('policy_family','UNKNOWN')
        groups=near_onset_groups(arr,max(1,int(mid.ticks_per_beat)//32)) if family=='GUITAR' else (exact_onset_groups(arr) if family in ('PIANO','ENSEMBLE','STRINGS','BRASS','ACCORDION') else [])
        for group in groups:
            model={'STRINGS':'profile_coherent_section_timing','BRASS':'profile_coherent_stab_timing','ACCORDION':'profile_coherent_bellows_chord_timing'}.get(family,'coherent_chord_timing' if family=='PIANO' else ('coherent_sustain_chord_timing' if family=='ENSEMBLE' else 'coherent_strum_timing'))
            address=ctx.identity.address() if ctx else ()
            # STRINGS/BRASS/ACCORDION grouping never creates a new target: it
            # only collapses already profile-authorized per-note proposals to
            # their median so a chord cannot be torn apart.
            profile_coherence=family in ('STRINGS','BRASS','ACCORDION')
            if not profile_coherence and not getattr(registry,'instrument_positive_model_allowed',lambda *_args:False)(family,address,model):
                for note in group:planned[note_id(note)]=0
                continue
            source=raw_planned if family=='ENSEMBLE' else planned
            values=sorted(source.get(note_id(note),0) for note in group);common=values[len(values)//2]
            lower=max(-note.onset for note in group);upper=min(track_ends[note.track_index]-note.off for note in group);common=max(lower,min(upper,common))
            for note in group:planned[note_id(note)]=common;planned_reason[note_id(note)]=model
        if getattr(config,'enable_rhythm_trill_correction',True) and not getattr(config,'trained_rhythm_only',False):
            for group in _trill_groups(arr,max(1,int(mid.ticks_per_beat)//2)):
                values=sorted(planned.get(note_id(note),0) for note in group);common=values[len(values)//2]
                lower=max(-note.onset for note in group);upper=min(track_ends[note.track_index]-note.off for note in group);common=max(lower,min(upper,common))
                for note in group:
                    planned[note_id(note)]=common;planned_reason[note_id(note)]='coherent_factory_trill_timing'
    for n,_ctx in active:
        if (n.track_index,n.channel) in controller_guard:planned[note_id(n)]=0;trained_gate[note_id(n)]=0
    drum=[n for n in notes if (lambda ctx:str(getattr(ctx,'family','')).upper()=='DRUM_KIT' or getattr(ctx,'role',None) in ('DRUM','PERC'))(contexts.get((n.track_index,n.channel)))];active_ids={note_id(n) for n,_ctx in active};anchor_groups=defaultdict(list)
    for n in notes:
        ctx=contexts.get((n.track_index,n.channel))
        if not ctx or str(ctx.family).upper()!='BASS' or not drum:continue
        anchor=min(drum,key=lambda item:abs(item.onset-n.onset))
        if abs(anchor.onset-n.onset)<=max(1,mid.ticks_per_beat//4):anchor_groups[note_id(anchor)].append((n,ctx,anchor))
    for anchor_key,pairs in anchor_groups.items():
        anchor=pairs[0][2];members=[anchor]+[row[0] for row in pairs]
        allowed=all(note_id(note) in active_ids and getattr(registry,'instrument_positive_model_allowed',lambda *_args:False)('BASS',ctx.identity.address(),'drum_anchor_timing') for note,ctx,_anchor in pairs)
        lower=max(-note.onset for note in members);upper=min(track_ends[note.track_index]-note.off for note in members)
        if any(note.off>=track_ends[note.track_index] for note in members):lower=max(lower,0)
        common=max(lower,min(upper,planned.get(anchor_key,0))) if allowed and anchor_key in active_ids else 0
        for note in members:planned[note_id(note)]=common;planned_reason[note_id(note)]='drum_anchor_timing' if allowed else 'bass_drum_lock_preserve'
    updates=defaultdict(dict)
    for n,_ctx in active:
        shift=planned.get(note_id(n),0)
        shift=max(-n.onset,min(shift,track_ends[n.track_index]-n.off))
        if n.off>=track_ends[n.track_index] and shift<0:shift=0
        gate_delta=trained_gate.get(note_id(n),0)
        gate_delta=int(round(gate_delta*float(policy_for(_ctx.family).get('gate_scale',1.0))))
        if not shift and not gate_delta:continue
        old_on=n.onset;old_off=n.off;new_on=max(0,n.onset+shift);new_off=new_on if n.off==n.onset else max(new_on+1,n.off+shift);updates[n.track_index][n.on_index]=new_on;updates[n.track_index][n.off_index]=new_off
        if shift:report.changes.append(Change(n.track_index,n.on_index,'timing',old_on,new_on,planned_reason.get(note_id(n),'profile_residual_guarded')+':'+n.intent,'',channel=n.channel,note=n.note,occurrence=n.occurrence,protected=n.protected))
        n.onset=new_on;n.off=new_off
        if old_off>=track_ends[n.track_index] and gate_delta<0:gate_delta=0
        gate_off=max(new_on+1,min(track_ends[n.track_index],new_off+gate_delta)) if old_off>old_on else new_off
        if gate_off!=new_off:
            updates[n.track_index][n.off_index]=gate_off;report.changes.append(Change(n.track_index,n.off_index,'gate',new_off,gate_off,trained_gate_reason.get(note_id(n),'explicit_trained_note_duration'),'trained_neural_performance',channel=n.channel,note=n.note,occurrence=n.occurrence,protected=n.protected));n.off=gate_off
    for ti,delta in updates.items():
        for event in track_events[ti]:
            if event[1] in delta:event[0]=delta[event[1]]
        mid.tracks[ti]=rebuild_track(track_events[ti])
