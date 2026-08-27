"""Per-note Factory evidence and runtime usage accounting."""
from __future__ import annotations

from collections import Counter, defaultdict

from ..instruments.policies import policy_for,profile_evidence_allows_mutation


def _note_id(note):return (note.track_index,note.channel,note.note,note.occurrence)


def _change_id(change):
    if None in (getattr(change,'channel',None),getattr(change,'note',None),getattr(change,'occurrence',None)):return None
    return (change.track,change.channel,change.note,change.occurrence)


def _profile_used(profile,drum_profile,policy,config):
    if not profile_evidence_allows_mutation(policy,profile or drum_profile):return False
    if drum_profile and (policy.get('velocity') or policy.get('timing')):return True
    if not profile:return False
    if policy.get('velocity') and config.enable_velocity and (profile.get('velocity') or profile.get('_velocity_modes')):return True
    if policy.get('timing') and config.enable_timing and config.timing_strength>0 and (profile.get('timing_residual_ticks') or profile.get('timing_residual')):return True
    if policy.get('gate') and config.enable_gate and config.gate_strength>0 and profile.get('gate_to_next_onset'):return True
    return False


def build_factory_usage_meter(notes,contexts,profiles,registry,changes,config):
    """Classify every note exactly once and aggregate evidence stages.

    Coverage classes are mutually exclusive.  Stage counters are cumulative:
    available -> resolved -> used -> mutated, while blocked records the safe
    terminal alternatives (protected/conflict/unknown/policy-disabled).
    """
    mutated_ids={key for key in (_change_id(change) for change in changes) if key is not None}
    classes=Counter();stages=Counter();families=defaultdict(Counter);roles=defaultdict(Counter);contexts_out={}
    blocked_mutations=[]
    for note in notes:
        key=(note.track_index,note.channel);ctx=contexts.get(key);profile=profiles.get(key);drum_profile=None;family='UNKNOWN';role='UNKNOWN';policy=policy_for('UNKNOWN');available=False;resolved=False;used=False;blocked_reason=None
        if ctx:
            family=ctx.family or 'UNKNOWN';role=ctx.role or 'UNKNOWN';policy=policy_for(family)
            if ctx.family=='DRUM_KIT' or ctx.role in ('DRUM','PERC'):
                drum_profile=registry.resolve_drum_key(ctx.identity.msb,ctx.identity.lsb,ctx.identity.program,note.note)
        manual_dnc=bool(ctx and ctx.identity.dnc_named);rx=bool(ctx and ctx.identity.rx_named)
        if ctx is None:
            classification='NO_CONTEXT';blocked_reason='no_context'
        elif ctx.identity.conflict:
            classification='IDENTITY_CONFLICT';blocked_reason='identity_conflict'
        elif note.protected and manual_dnc:
            classification='MANUAL_DNC_PROTECTED';available=True;resolved=True;blocked_reason='manual_dnc_protected'
        elif note.protected and rx:
            classification='RX_PROTECTED';available=bool(profile);resolved=bool(profile);blocked_reason='rx_protected'
        elif note.protected:
            classification='PROTECTED_NOTE';available=bool(profile or drum_profile);resolved=bool(profile or drum_profile);blocked_reason='protected'
        elif drum_profile:
            classification='EXACT_KIT_KEY';available=True;resolved=True;used=_profile_used(profile,drum_profile,policy,config)
        elif profile and str(profile.get('_velocity_semantics','')).endswith('ROLE_ELEMENT_CV'):
            classification='EXACT_CONTEXT';available=True;resolved=True;used=_profile_used(profile,None,policy,config)
        elif profile:
            classification='EXACT_SOUND';available=True;resolved=True;used=_profile_used(profile,None,policy,config)
        elif hasattr(registry,'velocity_family_profile') and registry.velocity_family_profile(family,role):
            classification='FAMILY_FALLBACK';available=True;used=bool(policy.get('velocity') and config.enable_velocity and config.enable_velocity_conductor)
        else:
            classification='UNKNOWN';blocked_reason='no_factory_evidence'
        if not blocked_reason and policy.get('exact_only') and not profile_evidence_allows_mutation(policy,profile or drum_profile):
            blocked_reason='insufficient_exact_evidence';used=False
        if not blocked_reason and not any(policy.get(name,False) for name in ('velocity','timing','gate')):
            blocked_reason='policy_disabled';used=False
        mutated=_note_id(note) in mutated_ids
        if mutated and blocked_reason:blocked_mutations.append({'track':note.track_index,'channel':note.channel+1,'note':note.note,'occurrence':note.occurrence,'classification':classification,'blocked_reason':blocked_reason})
        classes[classification]+=1;stages['total']+=1;stages['available']+=int(available);stages['resolved']+=int(resolved);stages['used']+=int(used);stages['mutated']+=int(mutated);stages['blocked']+=int(blocked_reason is not None)
        fam=families[family];fam['total']+=1;fam[classification]+=1;fam['available']+=int(available);fam['resolved']+=int(resolved);fam['used']+=int(used);fam['mutated']+=int(mutated);fam['blocked']+=int(blocked_reason is not None)
        rr=roles[role];rr['total']+=1;rr['mutated']+=int(mutated);rr['blocked']+=int(blocked_reason is not None)
        context_key=(note.track_index,note.channel)
        if context_key not in contexts_out:
            completeness=getattr(registry,'profile_completeness',lambda _profile:None)(profile)
            contexts_out[context_key]={'track':note.track_index,'channel':note.channel+1,'family':family,'role':role,'policy_family':policy.get('policy_family'),'profile_completeness':(completeness or {}).get('completion_state'),'explicit_unknowns':len((completeness or {}).get('unresolved',[])),'notes':0,'classification_counts':Counter(),'available':0,'resolved':0,'used':0,'mutated':0,'blocked':0}
        row=contexts_out[context_key];row['notes']+=1;row['classification_counts'][classification]+=1
        for name,value in [('available',available),('resolved',resolved),('used',used),('mutated',mutated),('blocked',blocked_reason is not None)]:row[name]+=int(value)
    total=stages['total'];coverage_sum=sum(classes.values());percentages={name:round(100*stages[name]/max(1,total),4) for name in ('available','resolved','used','mutated','blocked')}
    family_rows=[]
    for family,row in sorted(families.items(),key=lambda item:(-item[1]['total'],item[0])):
        family_rows.append({'family':family,**dict(row),'coverage_percent':round(100*row['total']/max(1,total),4)})
    context_rows=[]
    for _key,row in sorted(contexts_out.items()):row=dict(row);row['classification_counts']=dict(sorted(row['classification_counts'].items()));context_rows.append(row)
    return {'schema':'PA800_FACTORY_USAGE_METER_V1','notes_total':total,'classification_counts':dict(sorted(classes.items())),'stage_counts':dict(stages),'stage_percentages':percentages,'by_family':family_rows,'by_role':[{'role':role,**dict(row)} for role,row in sorted(roles.items())],'contexts':context_rows,'blocked_mutation_samples':blocked_mutations[:32],'blocked_mutation_count':len(blocked_mutations),'invariants':{'classification_sum':coverage_sum,'classification_equals_total':coverage_sum==total,'no_blocked_note_mutated':not blocked_mutations},'pass':coverage_sum==total and not blocked_mutations}


def render_factory_usage_dashboard(meter):
    """Compact, deterministic text dashboard for GUI and support reports."""
    stages=meter.get('stage_counts',{});percent=meter.get('stage_percentages',{});lines=[
        'FACTORY USAGE METER — '+('PASS' if meter.get('pass') else 'FAIL'),
        '='*78,
        f"Notes: {meter.get('notes_total',0):,}",
        '',
        'EVIDENCE PIPELINE',
    ]
    for name in ('available','resolved','used','mutated','blocked'):
        lines.append(f"  {name.upper():10s} {int(stages.get(name,0)):8,d}  {float(percent.get(name,0)):.2f}%")
    lines.extend(['','COVERAGE CLASSES'])
    for name,count in sorted(meter.get('classification_counts',{}).items(),key=lambda item:(-item[1],item[0])):lines.append(f"  {name:28s} {int(count):8,d}")
    lines.extend(['','INSTRUMENT FAMILIES'])
    for row in meter.get('by_family',[]):
        lines.append(f"  {str(row.get('family')):20s} notes={int(row.get('total',0)):7,d} coverage={float(row.get('coverage_percent',0)):6.2f}% used={int(row.get('used',0)):7,d} mutated={int(row.get('mutated',0)):7,d} blocked={int(row.get('blocked',0)):7,d}")
    lines.extend(['','TRACK / CHANNEL CONTEXTS'])
    for row in meter.get('contexts',[]):
        lines.append(f"  T{row.get('track')} CH{row.get('channel')} {row.get('family')}/{row.get('role')}: notes={row.get('notes')} used={row.get('used')} changed={row.get('mutated')} blocked={row.get('blocked')} profile={row.get('profile_completeness') or 'N/A'} unknowns={row.get('explicit_unknowns',0)}")
    blocked=int(meter.get('blocked_mutation_count',0))
    lines.extend(['',f"SAFETY: blocked-note mutations={blocked}; classification sum={meter.get('invariants',{}).get('classification_sum')} / {meter.get('notes_total',0)}"])
    if blocked:
        lines.append('CRITICAL: at least one mutation crossed a protected/unknown boundary.')
        for row in meter.get('blocked_mutation_samples',[]):lines.append('  '+repr(row))
    return '\n'.join(lines)+'\n'