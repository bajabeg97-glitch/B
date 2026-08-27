from collections import defaultdict
from ..utils import quantiles, piecewise_map, clamp, stable_seed, deterministic_gauss
from ..models import Change
from ..instruments.policies import policy_for,profile_evidence_allows_mutation
from ..instruments.guards import exact_onset_groups,expressive_controller_channels,near_onset_groups,phrase_groups,retain_group_spread,retain_group_velocity_shape

FAMILY_PROFILE_MAX_DELTA={'ORGAN':4,'STRINGS':12,'ENSEMBLE':12,'SYNTH_PAD':10,'CHOIR_VOICE':10,'BRASS':16,'REED':14,'PIPE':14,'HARMONICA':12,'ACCORDION':12,'SYNTH_LEAD':14}

def _apply_group(mid, key, arr, ctx, prof, registry, config, report, label, controller_guard=frozenset()):
    if not prof or len(arr)<4:return
    vals=[n.velocity for n in arr]; q=quantiles(vals)
    pv=prof.get('velocity',{}) or {}
    dst=[pv.get('working_min',q[0]),pv.get('ideal_min',q[1]),pv.get('ideal_center',q[2]),pv.get('ideal_max',q[3]),pv.get('working_max',q[4])]
    src=list(q); spread=max(1.0,float(dst[3])-float(dst[1])); sigma=min(4.5,max(0.6,spread/8.0))*config.velocity_random_strength
    # p05/p95 are soft safety rails; working_min/max are targets, not hard
    # clamps. This keeps quiet/loud expression instead of flattening tails.
    lo=int(max(1,pv.get('p05',pv.get('working_min',1)))); hi=int(min(127,pv.get('p95',pv.get('working_max',127)))); tr=mid.tracks[key[0]]
    policy=policy_for(ctx.family);proposed=[]
    for n in arr:
        target=piecewise_map(n.velocity,src,dst)
        modes=[float(x.get('center')) for x in prof.get('_velocity_modes',[]) if x.get('center') is not None]
        if modes:
            nearest=min(modes,key=lambda x:abs(x-target))
            target += (nearest-target)*(0.10+0.15*config.velocity_strength)
        blended=n.velocity+(target-n.velocity)*config.velocity_strength
        jitter=0.0 if policy.get('phrase_first') or policy.get('velocity_limited') else deterministic_gauss(stable_seed(config.seed,key,n.note,n.onset,n.on_index,n.intent,label),0,sigma)
        factor=0.55 if n.intent in ('METRIC_MAIN','METRIC_ANCHOR','PHRASE_ACCENT') else (1.15 if 'PASSING' in n.intent or 'SECONDARY' in n.intent else 1.0)
        candidate=int(round(clamp(blended+jitter*factor,lo,hi)));cap=FAMILY_PROFILE_MAX_DELTA.get(policy.get('policy_family'))
        if cap is not None:candidate=int(clamp(candidate,n.velocity-cap,n.velocity+cap))
        proposed.append(candidate)
    family=str(ctx.family).upper();model_ids={}
    address=ctx.identity.address();positive=getattr(registry,'instrument_positive_model_allowed',lambda *_args:False)
    if family=='PIANO':
        if positive(family,address,'coherent_chord_velocity'):
            chord_groups=exact_onset_groups(arr);proposed=retain_group_velocity_shape(arr,proposed,chord_groups,lo,hi);proposed=retain_group_spread(arr,proposed,.95,lo,hi)
            model_ids.update({id(note):'coherent_chord_velocity' for group in chord_groups for note in group})
        else:proposed=retain_group_spread(arr,proposed,.75,lo,hi)
    elif family=='GUITAR':
        groups=near_onset_groups(arr,max(1,int(mid.ticks_per_beat)//32));grouped={id(note) for group in groups for note in group}
        for index,note in enumerate(arr):
            if id(note) in grouped:proposed[index]=note.velocity
    elif family=='ENSEMBLE' and positive(family,address,'coherent_phrase_velocity'):
        groups=phrase_groups(arr,mid.ticks_per_beat)
        proposed=retain_group_velocity_shape(arr,proposed,groups,lo,hi)
        model_ids.update({id(note):'coherent_phrase_velocity' for group in groups for note in group})
    elif family=='REED' and positive(family,address,'breath_phrase_velocity'):
        if key in controller_guard:
            proposed=[note.velocity for note in arr]
        else:
            groups=phrase_groups(arr,mid.ticks_per_beat)
            proposed=retain_group_velocity_shape(arr,proposed,groups,lo,hi)
            model_ids.update({id(note):'breath_phrase_velocity' for group in groups for note in group})
    for n,new in zip(arr,proposed):
        if new!=n.velocity:
            old=n.velocity; tr[n.on_index]=tr[n.on_index].copy(velocity=new); n.velocity=new
            # Velocity authority remains exclusively the resolved Factory/Gold
            # profile; family metadata only makes the audit reason explicit.
            reason='profile_curve+deterministic_residual:%s:%s:%s'%(policy.get('policy_family','UNKNOWN'),policy.get('group_mode','UNKNOWN'),n.intent)
            if id(n) in model_ids:reason+='+'+model_ids[id(n)]
            report.changes.append(Change(key[0],n.on_index,'velocity',old,new,reason,label,channel=n.channel,note=n.note,occurrence=n.occurrence,protected=n.protected))

def optimize_velocity(mid, notes, contexts, profiles, registry, config, report):
    if not config.enable_velocity:return
    controller_guard=expressive_controller_channels(mid,contexts)
    groups=defaultdict(list)
    for n in notes:
        if not n.protected: groups[(n.track_index,n.channel)].append(n)
    for key,arr in groups.items():
        ctx=contexts.get(key); parent=profiles.get(key)
        if not ctx or ctx.identity.conflict:continue
        policy=policy_for(ctx.family)
        if not policy.get('velocity',False) or not profile_evidence_allows_mutation(policy,parent):continue
        if policy.get('protect_pb_cc1') and key in controller_guard:continue
        if ctx.family=='DRUM_KIT' or ctx.role in ('DRUM','PERC'):
            bynote=defaultdict(list)
            for n in arr:bynote[n.note].append(n)
            for note,sub in bynote.items():
                dp=registry.resolve_drum_key(ctx.identity.msb,ctx.identity.lsb,ctx.identity.program,note)
                prof=dp or parent
                label='%s.%s.%s %s KEY_%03d' % (ctx.identity.msb,ctx.identity.lsb,ctx.identity.program,ctx.identity.name or '',note)
                _apply_group(mid,key,sub,ctx,prof,registry,config,report,label,controller_guard)
        else:
            label='%s.%s.%s %s%s' % (ctx.identity.msb,ctx.identity.lsb,ctx.identity.program,ctx.identity.name or '',('/'+parent.get('_element_override')) if parent and parent.get('_element_override') else '')
            _apply_group(mid,key,arr,ctx,parent,registry,config,report,label,controller_guard)
