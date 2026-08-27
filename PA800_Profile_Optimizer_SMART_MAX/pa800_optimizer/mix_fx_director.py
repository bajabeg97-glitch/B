"""Single-pass ensemble-aware CC91/CC93 director.

The director never creates effect events and never touches Pa800 Insert/Master
routing.  It may only move existing send contours by a bounded common offset.
Without E3 hardware evidence it is a protective dry-only pass; creative depth
and section-dependent wetness require a safe-auto/auto hardware record.
"""
from __future__ import annotations

from collections import defaultdict
import statistics

from .hardware_evidence import HardwareEvidenceRegistry
from .intelligence.sound_fx import fx_profile_for,normalize_family


FUNCTION_TARGETS={
    'FOUNDATION_DRUM':(16,0),'FOUNDATION_PERC':(15,0),'FOUNDATION_BASS':(4,0),
    'LEAD':(19,3),'COUNTER_LINE':(21,4),'RIFF_OSTINATO':(16,4),
    'HARMONIC_COMP':(23,6),'PAD_BACKGROUND':(31,11),'ORNAMENT_FX':(12,0),
    'UNKNOWN':(16,2),
}
FOUNDATION={'FOUNDATION_DRUM','FOUNDATION_PERC','FOUNDATION_BASS'}
BACKGROUND={'HARMONIC_COMP','PAD_BACKGROUND'}


def _median(values,default=0.0):return float(statistics.median(values)) if values else float(default)


def _section_for_tick(sections,tick):
    for section in sections:
        if int(section.get('start_tick',0))<=tick<int(section.get('end_tick',tick+1)):return section
    return sections[-1] if sections else {'index':0,'label':'WHOLE','evidence_level':'E0'}


def _events(mid,ctx):
    tick=0;rows=[];occurrences=defaultdict(int)
    for index,msg in enumerate(mid.tracks[ctx.track_index]):
        tick+=int(msg.time)
        if getattr(msg,'channel',None)==ctx.channel and msg.type=='control_change' and msg.control in (91,93):
            occurrence=occurrences[msg.control];occurrences[msg.control]+=1
            rows.append({'index':index,'tick':tick,'control':msg.control,'value':msg.value,'occurrence':occurrence})
    return rows


def _recommendation_map(recommendations):
    return {(int(row.get('track',-1)),int(row.get('channel',0))-1):row for row in recommendations or []}


def _function_map(musical_context):
    return {(int(row['track']),int(row['channel'])-1):row for row in musical_context.get('track_functions',[])}


def _ensemble_map(musical_context):
    return {int(row.get('section_index',0)):row for row in musical_context.get('ensemble_sections',[])}


def _part_for(ensemble,key):
    track,channel=key
    for part in ensemble.get('parts',[]):
        if int(part.get('track',-1))==track and int(part.get('channel',0))-1==channel:return part
    return None


def _base_target(ctx,function,recommendation):
    fx=(recommendation or {}).get('fx') or fx_profile_for(ctx.family,ctx.identity.name,ctx.role)
    family_reverb=int(fx.get('reverb',0));family_chorus=int(fx.get('chorus',0));fr,fc=FUNCTION_TARGETS.get(function,FUNCTION_TARGETS['UNKNOWN'])
    return int(round(.62*family_reverb+.38*fr)),int(round(.62*family_chorus+.38*fc))


def _section_target(base,function,section,ensemble,key):
    reverb,chorus=base;reasons=[];label=str(section.get('label','')).upper();part=_part_for(ensemble,key);parts=ensemble.get('parts',[])
    density=sum(float(row.get('density',0)) for row in parts);active=len(parts)
    if density>=12 or active>=8:reverb-=4;chorus-=2;reasons.append('dense_ensemble_headroom')
    elif density>=7 or active>=6:reverb-=2;chorus-=1;reasons.append('busy_ensemble_clarity')
    if label in ('CHORUS','VARIATION 4','FILL 1','FILL 2','BREAK') and density>=6:reverb-=2;reasons.append('high_energy_section_clarity')
    elif label in ('INTRO','ENDING') and density<6:reverb+=2;reasons.append('sparse_boundary_depth')
    focus=ensemble.get('focus') or {};focus_key=(focus.get('track'),int(focus.get('channel',0))-1 if focus.get('channel') is not None else None)
    if function in BACKGROUND:
        if ensemble.get('masking_alerts'):reverb-=3;chorus-=2;reasons.append('background_masking_guard')
        if focus_key==key and len(parts)>2:reverb-=2;reasons.append('background_false_focus_guard')
    if function=='LEAD':
        margin=ensemble.get('focus_energy_margin_over_background')
        if margin is not None and float(margin)<4:reverb-=3;chorus-=1;reasons.append('lead_clarity_guard')
    if function=='FOUNDATION_BASS':reverb=min(reverb,5);chorus=0;reasons.append('bass_dry_cap')
    elif function in ('FOUNDATION_DRUM','FOUNDATION_PERC'):reverb=min(reverb,18);chorus=0;reasons.append('rhythm_transient_cap')
    if part and float(part.get('energy',0))>=112:reverb-=2;reasons.append('high_energy_headroom')
    return (max(0,min(48,reverb)),max(0,min(32,chorus))),reasons,{'active_parts':active,'combined_density':round(density,3),'section_label':section.get('label')}


def run_mix_fx_director(mid,contexts,musical_context,recommendations,config):
    enabled=bool(getattr(config,'enable_mix_fx_director',True));policy=str(getattr(config,'mix_fx_policy','auto') or 'auto').lower()
    requested_apply=bool(getattr(config,'apply_mix_fx_director',False))
    if policy=='apply':requested_apply=True
    elif policy in ('off','shadow'):requested_apply=False
    elif policy=='auto':requested_apply=bool(getattr(config,'apply_existing_fx_sends',False) and not getattr(config,'preserve_controllers',True))
    if not enabled or policy=='off':return {'schema':'PA800_MIX_FX_DIRECTOR_V1','enabled':False,'policy':'off','mutations':0,'contexts':[]},set(),{}
    functions=_function_map(musical_context);sections=musical_context.get('sections',[]);ensembles=_ensemble_map(musical_context);rec_map=_recommendation_map(recommendations);hardware=HardwareEvidenceRegistry(getattr(config,'hardware_evidence_path',None));audit=[];authorized=set();updates={};event_mutations=[]
    for key,ctx in sorted(contexts.items()):
        function=functions.get(key,{}).get('function','UNKNOWN');events=_events(mid,ctx);base=_base_target(ctx,function,rec_map.get(key));approval=hardware.fx_approval(ctx.identity.address(),normalize_family(ctx.family,ctx.identity.name),'section');e3=bool(approval and approval.get('approval') in ('safe-auto','auto'))
        sensitive=bool(ctx.identity.rx_named or ctx.identity.dnc_named or ctx.identity.conflict or normalize_family(ctx.family,ctx.identity.name) in ('UNKNOWN','SFX'))
        section_rows=[]
        for section in sections or [{'index':0,'label':'WHOLE','start_tick':0,'end_tick':10**18,'evidence_level':'E0'}]:
            target,reasons,metrics=_section_target(base,function,section,ensembles.get(int(section.get('index',0)),{}),key)
            section_rows.append({'section_index':section.get('index',0),'section_label':section.get('label'),'section_evidence':section.get('evidence_level','E0'),'target_cc91':target[0],'target_cc93':target[1],'reasons':reasons,'metrics':metrics})
        changes=0;control_audit=[];apply_status='shadow_only'
        if not events:apply_status='recommendation_only_no_existing_cc91_cc93'
        elif sensitive:apply_status='blocked_sensitive_unknown_or_conflict'
        elif requested_apply:
            # Only E3 permits creative wet increases and per-section Song
            # movement.  The non-E3 path is a whole-channel dry/headroom guard.
            groups=defaultdict(list)
            for event in events:
                section=_section_for_tick(sections,event['tick']);scope=int(section.get('index',0)) if e3 else -1;groups[(event['control'],scope)].append((event,section))
            cap=12 if e3 else 8
            for (control,scope),rows in groups.items():
                center=_median([event['value'] for event,_ in rows]);targets=[]
                for _event,section in rows:
                    section_row=next((row for row in section_rows if row['section_index']==section.get('index',0)),section_rows[0])
                    targets.append(section_row['target_cc91' if control==91 else 'target_cc93'])
                target=_median(targets,center);delta=int(round((target-center)*.28));delta=max(-cap,min(cap,delta))
                if not e3:delta=min(0,delta)
                before=[];after=[]
                for event,_section in rows:
                    msg=mid.tracks[ctx.track_index][event['index']];new=max(0,min(127,msg.value+delta));before.append(msg.value);after.append(new)
                    if new!=msg.value:
                        mid.tracks[ctx.track_index][event['index']]=msg.copy(value=new);changes+=1
                        event_mutations.append({'track':ctx.track_index,'channel':ctx.channel,'control':control,'occurrence':event['occurrence'],'tick':event['tick'],'old':msg.value,'new':new,'source':'mix_fx_director'})
                control_audit.append({'control':control,'scope':'section' if e3 else 'whole_channel','section_index':None if scope==-1 else scope,'center_before':round(center,3),'target':round(target,3),'delta':delta,'events':len(rows),'min_before':min(before),'max_before':max(before),'min_after':min(after),'max_after':max(after),'contour_preserved':all((b2-b1)==(a2-a1) for b1,b2,a1,a2 in zip(before,before[1:],after,after[1:]))})
            apply_status='applied_e3_section_depth' if changes and e3 else 'applied_bounded_dry_guard' if changes else 'already_safe_or_wet_increase_requires_e3'
        if changes:authorized.add(key)
        evidence='E3' if e3 else 'E2' if ctx.content_type=='style' and any(row['section_evidence']=='E2' for row in section_rows) else 'E1'
        row={'track':ctx.track_index,'channel':ctx.channel+1,'sound':ctx.identity.name,'family':ctx.family,'function':function,'base_target':{'cc91':base[0],'cc93':base[1]},'existing_events':len(events),'changes':changes,'apply_status':apply_status,'evidence_level':evidence,'hardware_approval':None if not approval else approval.get('approval'),'section_depth_authority':e3,'sections':section_rows,'control_audit':control_audit}
        audit.append(row);updates[key]={'fx_send_changes':changes,'fx_apply_status':apply_status,'mix_fx_evidence_level':evidence,'mix_fx_hardware_approval':row['hardware_approval']}
    total=sum(row['changes'] for row in audit)
    result={'schema':'PA800_MIX_FX_DIRECTOR_V1','enabled':True,'policy':'apply' if requested_apply else 'shadow','apply_requested':requested_apply,'insert_master_routing':'locked_recommendation_only','creates_controller_events':False,'hardware_evidence':hardware.summary(),'contexts':audit,'mutations':total,'authorized_channels':len(authorized),'event_mutations':event_mutations,'summary':{'contexts':len(audit),'existing_send_events':sum(row['existing_events'] for row in audit),'changed_events':total,'e3_contexts':sum(row['evidence_level']=='E3' for row in audit),'blocked_sensitive':sum(row['apply_status']=='blocked_sensitive_unknown_or_conflict' for row in audit),'headroom_guards':sum(any('headroom' in reason for section in row['sections'] for reason in section['reasons']) for row in audit)}}
    return result,authorized,updates