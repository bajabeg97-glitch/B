"""Post-proposal mutation arbitration and conflict audit.

Existing mature engines still execute transactionally inside Optimizer.  This
arbiter gives the central brain a single ledger of overlapping proposals and
fails closed on contradictory mutation classes or impossible event identity.
"""
from __future__ import annotations

from collections import defaultdict, Counter

VELOCITY_KINDS = {'velocity', 'velocity_conductor', 'velocity_budget', 'performance_velocity', 'baja_percussion_40pct'}
TIMING_KINDS = {'timing'}
GATE_KINDS = {'gate'}
KNOWN_KINDS = VELOCITY_KINDS | TIMING_KINDS | GATE_KINDS


def _event_key(change):
    return (int(change.track), None if change.channel is None else int(change.channel), change.note, change.occurrence)


def audit_mutation_arbitration(changes):
    groups = defaultdict(list)
    unknown = []
    for index, change in enumerate(changes or []):
        kind = str(getattr(change, 'kind', ''))
        if kind not in KNOWN_KINDS:
            # Non-note/controller/sound mutation classes are owned by their
            # dedicated verifier ledgers and are not rejected here.
            continue
        if change.note is None or change.occurrence is None or change.channel is None:
            unknown.append({'index': index, 'kind': kind, 'reason': 'missing_stable_note_identity'})
            continue
        groups[_event_key(change)].append((index, change))
    conflicts = []
    stacked = []
    for key, rows in sorted(groups.items()):
        kinds = [str(row.kind) for _, row in rows]
        families = set('velocity' if k in VELOCITY_KINDS else 'timing' if k in TIMING_KINDS else 'gate' for k in kinds)
        if len(rows) > 1:
            stacked.append({'event_key': list(key), 'changes': len(rows), 'kinds': kinds, 'families': sorted(families)})
        # Multiple velocity stages are expected and bounded cumulatively; timing
        # and gate can coexist because they address independent dimensions.
        # A single event receiving multiple timing or multiple gate rewrites is
        # suspicious and must be visible to the release gate.
        counts = Counter('velocity' if k in VELOCITY_KINDS else k for k in kinds)
        for family in ('timing', 'gate'):
            if counts.get(family, 0) > 1:
                conflicts.append({'event_key': list(key), 'family': family, 'count': counts[family], 'reason': 'duplicate_dimension_mutation'})
    return {
        'schema': 'PA800_MUTATION_ARBITER_V1',
        'events_with_note_mutations': len(groups),
        'stacked_events': len(stacked),
        'stacked_samples': stacked[:50],
        'identity_violations': unknown[:50],
        'conflicts': conflicts[:50],
        'pass': not unknown and not conflicts,
    }


def build_pre_apply_mutation_policy(decision_plan, config):
    """Resolve mutation-dimension ownership before engines execute.

    This does not create edits. It makes the execution contract explicit so a
    neural advisor cannot silently acquire velocity/sound/pitch authority and
    overlapping deterministic stages have a stable, testable order.
    """
    neural_requested=bool(getattr(config,'apply_trained_rhythm_model',False))
    tracks=[]
    for row in (decision_plan or {}).get('tracks',[]) or []:
        preserve=str(row.get('action'))=='PRESERVE' or str(row.get('ood_status'))=='HARD_PRESERVE'
        tracks.append({
            'track':int(row.get('track')), 'channel':int(row.get('channel')),
            'action':row.get('action'), 'ood_status':row.get('ood_status'),
            'dimensions':{
                'pitch':{'owner':'PRESERVE','allowed':False},
                'harmony':{'owner':'PRESERVE','allowed':False},
                'sound':{'owner':'SOUND_KIT_SELECTOR','allowed':not preserve},
                'velocity':{'owner':'FACTORY_GOLD_DETERMINISTIC','allowed':not preserve},
                'timing':{'owner':'NEURAL_ADVISOR_THEN_FACTORY_GOLD' if neural_requested else 'FACTORY_GOLD_DETERMINISTIC','allowed':not preserve},
                'gate':{'owner':'NEURAL_ADVISOR_THEN_FACTORY_GOLD' if neural_requested else 'FACTORY_GOLD_DETERMINISTIC','allowed':not preserve},
            },
            'stage_order':['VELOCITY','PERFORMANCE_DIRECTOR','TIMING','GATE','BAJA_STAGE'],
        })
    return {
        'schema':'PA800_PRE_APPLY_MUTATION_POLICY_V2',
        'neural_requested':neural_requested,
        'neural_allowed_dimensions':['timing','gate'] if neural_requested else [],
        'neural_forbidden_dimensions':['pitch','harmony','sound','velocity'],
        'tracks':tracks,
        'pass':all(not item['dimensions']['pitch']['allowed'] and not item['dimensions']['harmony']['allowed'] for item in tracks),
    }



def build_proposal_arbitration(decision_plan, config):
    """Build and resolve track/dimension mutation proposals before execution.

    The V3 contract is intentionally deterministic.  It does not fabricate
    per-note edits; it resolves *who may propose/apply* each mutation dimension
    for each track before mutable engines receive their note set.
    """
    neural_requested=bool(getattr(config,'apply_trained_rhythm_model',False))
    rows=[]; accepted=0; rejected=0; conflicts=[]
    for track in (decision_plan or {}).get('tracks',[]) or []:
        key=(int(track.get('track')), int(track.get('channel'))-1)
        preserve=str(track.get('action'))=='PRESERVE' or str(track.get('ood_status')) in ('HARD_PRESERVE','OOD')
        proposals=[]
        def add(dimension, source, priority, requested=True, reason=''):
            nonlocal accepted,rejected
            requested=bool(requested)
            allowed=bool(requested and not preserve and dimension not in ('pitch','harmony'))
            row={'dimension':dimension,'source':source,'priority':int(priority),'requested':requested,
                 'allowed':allowed,'reason':reason or ('preserve_or_ood' if preserve else 'authority_candidate')}
            proposals.append(row)
            if requested:
                accepted += int(allowed); rejected += int(not allowed)
        add('velocity','FACTORY_GOLD_DETERMINISTIC',100,getattr(config,'enable_velocity',False),'resolved profile authority')
        add('timing','FACTORY_GOLD_DETERMINISTIC',80,getattr(config,'enable_timing',False),'deterministic fallback authority')
        add('gate','FACTORY_GOLD_DETERMINISTIC',80,getattr(config,'enable_gate',False),'deterministic fallback authority')
        add('timing','NEURAL_ADVISOR',90,neural_requested and getattr(config,'enable_timing',False),'advisor only; must pass deterministic guards')
        add('gate','NEURAL_ADVISOR',90,neural_requested and getattr(config,'enable_timing',False),'duration head rides with trained timing model; must pass deterministic guards')
        add('pitch','PRESERVE',1000,False,'immutable in normal optimization')
        add('harmony','PRESERVE',1000,False,'immutable in normal optimization')
        by_dim=defaultdict(list)
        for proposal in proposals:
            if proposal['requested']: by_dim[proposal['dimension']].append(proposal)
        resolved={}
        for dim,candidates in by_dim.items():
            allowed=[x for x in candidates if x['allowed']]
            if not allowed:
                resolved[dim]={'allowed':False,'winner':'PRESERVE','candidates':[x['source'] for x in candidates]}
                continue
            ordered=sorted(allowed,key=lambda x:(-x['priority'],x['source']))
            winner=ordered[0]
            # Neural may lead timing/gate proposal generation, but deterministic
            # Factory/Gold remains the mandatory verifier/fallback chain.
            chain=[x['source'] for x in ordered]
            resolved[dim]={'allowed':True,'winner':winner['source'],'authority_chain':chain,'candidates':[x['source'] for x in candidates]}
            if dim in ('velocity','pitch','harmony') and len({x['source'] for x in allowed})>1:
                conflicts.append({'track':key[0],'channel':key[1]+1,'dimension':dim,'sources':sorted({x['source'] for x in allowed}),'reason':'exclusive_dimension_competition'})
        rows.append({'track':key[0],'channel':key[1]+1,'action':track.get('action'),'ood_status':track.get('ood_status'),
                     'proposals':proposals,'resolved':resolved,
                     'execution_allowed':{dim:bool(resolved.get(dim,{}).get('allowed',False)) for dim in ('velocity','timing','gate','pitch','harmony')}})
    return {'schema':'PA800_MUTATION_PROPOSAL_ARBITER_V3','tracks':rows,'accepted_proposals':accepted,
            'rejected_proposals':rejected,'conflicts':conflicts[:50],'pass':not conflicts}


def proposal_dimension_allowed(arbitration, track, channel_zero_based, dimension):
    for row in (arbitration or {}).get('tracks',[]) or []:
        if int(row.get('track'))==int(track) and int(row.get('channel'))-1==int(channel_zero_based):
            return bool((row.get('execution_allowed') or {}).get(str(dimension),False))
    return False


def filter_notes_by_proposal(notes, arbitration, dimension):
    """Return only notes whose track/dimension was authorized pre-apply."""
    return [note for note in (notes or []) if proposal_dimension_allowed(arbitration,note.track_index,note.channel,dimension)]
