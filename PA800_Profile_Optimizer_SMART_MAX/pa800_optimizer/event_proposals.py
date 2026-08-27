"""Transactional event proposal generation and commit.

Mature velocity/timing/gate engines are executed against isolated MIDI copies.
Their effects are converted to stable per-note proposals before the production
MIDI is touched.  A deterministic arbiter then resolves each note dimension and
one shared commit mutates the real MIDI.
"""
from __future__ import annotations

import copy
from dataclasses import asdict
from collections import defaultdict

from .models import OptimizationReport, Change
from .core.midi_io import extract_notes, absolute_track, rebuild_track
from .analysis.intent import classify_intents
from .engines.velocity import optimize_velocity
from .engines.timing import optimize_timing
from .engines.gate import optimize_gate
from .engines.velocity_conductor import normalize_velocity
from .engines.performance_director import run_performance_director
from .user_stage_profile import apply_percussion_40_percent
from .instruments.policies import FAMILY_CUMULATIVE_VELOCITY_CAP, policy_for
from .mix_fx_director import run_mix_fx_director


def _key(note):
    return (int(note.track_index), int(note.channel), int(note.note), int(note.occurrence))


def _copy_note_semantics(source_notes, target_notes):
    source={_key(note):note for note in source_notes or []}
    for note in target_notes:
        ref=source.get(_key(note))
        if ref is None:
            # The caller already applied proposal/track authority filtering.
            # Notes outside that authorized set are hard-preserved in sandbox.
            note.protected=True
            continue
        note.protected=bool(ref.protected)
        note.intent=str(ref.intent)


def _temp_report():
    return OptimizationReport('<proposal-sandbox>','<proposal-sandbox>')


def _proposal_rows(before_notes, after_notes, dimension, source, temp_report):
    before={_key(note):note for note in before_notes}
    after={_key(note):note for note in after_notes}
    reasons=defaultdict(list)
    for change in temp_report.changes:
        if change.channel is None or change.note is None or change.occurrence is None:
            continue
        reasons[(int(change.track),int(change.channel),int(change.note),int(change.occurrence))].append({
            'kind':str(change.kind),'reason':str(change.reason),'profile':str(change.profile or '')})
    rows=[]
    for key,old in before.items():
        new=after.get(key)
        if new is None:
            continue
        row={
            'event_key':list(key),
            'track':old.track_index,'channel':old.channel,'note':old.note,'occurrence':old.occurrence,
            'on_index':old.on_index,'off_index':old.off_index,
            'source':source,'dimension':dimension,'protected':bool(old.protected),
            'old_velocity':old.velocity,'new_velocity':new.velocity,
            'old_onset':old.onset,'new_onset':new.onset,
            'old_duration':old.duration,'new_duration':new.duration,
            'reasons':reasons.get(key,[]),
            'change_kinds':[item.get('kind') for item in reasons.get(key,[])],
            'final_change_kind':(reasons.get(key,[])[-1].get('kind') if reasons.get(key) else None),
        }
        if dimension=='velocity' and new.velocity!=old.velocity:
            row['delta']=int(new.velocity-old.velocity);rows.append(row)
        elif dimension=='timing':
            onset_delta=int(new.onset-old.onset)
            duration_delta=int(new.duration-old.duration)
            if onset_delta:
                item=dict(row);item['dimension']='timing';item['delta']=onset_delta;rows.append(item)
            # optimize_timing may also carry a neural duration proposal. Keep it
            # as a distinct gate candidate so the final arbiter can compare it
            # with the dedicated deterministic gate engine.
            if duration_delta:
                item=dict(row);item['dimension']='gate';item['source']=source+'_DURATION';item['delta']=duration_delta;rows.append(item)
        elif dimension=='gate' and new.duration!=old.duration:
            row['delta']=int(new.duration-old.duration);rows.append(row)
    return rows


def generate_dimension_proposals(mid, notes, contexts, profiles, registry, config, dimension):
    """Run one mature engine in isolation and return event proposals + summary."""
    sandbox=copy.deepcopy(mid)
    sandbox_notes=extract_notes(sandbox)
    classify_intents(sandbox_notes,contexts,sandbox.ticks_per_beat)
    _copy_note_semantics(notes,sandbox_notes)
    before=copy.deepcopy(sandbox_notes)
    temp=_temp_report()
    if dimension=='velocity':
        optimize_velocity(sandbox,sandbox_notes,contexts,profiles,registry,config,temp)
        source='VELOCITY_ENGINE'
    elif dimension=='timing':
        optimize_timing(sandbox,sandbox_notes,contexts,profiles,registry,config,temp)
        source='NEURAL_TIMING_ENGINE' if bool(getattr(config,'apply_trained_rhythm_model',False)) else 'TIMING_ENGINE'
    elif dimension=='gate':
        optimize_gate(sandbox,sandbox_notes,contexts,profiles,config,temp)
        source='GATE_ENGINE'
    else:
        raise ValueError('Unsupported proposal dimension: %s'%dimension)
    after=extract_notes(sandbox)
    classify_intents(after,contexts,sandbox.ticks_per_beat)
    rows=_proposal_rows(before,after,dimension,source,temp)
    return rows,{
        'dimension':dimension,'source':source,'proposals':len(rows),
        'sandbox_changes':len(temp.changes),'workstation':copy.deepcopy(temp.workstation),
    }


def arbitrate_event_proposals(proposals, track_arbitration, decision_plan=None):
    """Resolve competing event proposals without touching MIDI.

    Velocity is exclusive deterministic authority. Timing is one onset delta.
    Gate chooses neural duration when explicitly present, otherwise the
    dedicated gate engine. Hard-preserve/OOD tracks are rejected again here.
    """
    grouped=defaultdict(lambda:defaultdict(list))
    rejected=[]
    for row in proposals or []:
        key=tuple(row['event_key']);dim=str(row['dimension'])
        # Track-level authority is a mandatory second gate.
        from .mutation_arbiter import proposal_dimension_allowed
        if not proposal_dimension_allowed(track_arbitration,row['track'],row['channel'],dim):
            rejected.append({**row,'rejection_reason':'track_dimension_not_authorized'});continue
        if row.get('protected'):
            rejected.append({**row,'rejection_reason':'protected_note'});continue
        grouped[key][dim].append(row)
    accepted=[];conflicts=[]
    for key,dimensions in sorted(grouped.items()):
        for dim,candidates in dimensions.items():
            if dim=='velocity':
                rank={'PERFORMANCE_REFINER_PIPELINE':120,'VELOCITY_ENGINE':100}
            elif dim=='timing':
                rank={'NEURAL_TIMING_ENGINE':100,'TIMING_ENGINE':90}
            else:
                rank={'NEURAL_TIMING_ENGINE_DURATION':100,'TIMING_ENGINE_DURATION':85,'GATE_ENGINE':90}
            ordered=sorted(candidates,key=lambda row:(-rank.get(str(row['source']),0),str(row['source'])))
            winner=ordered[0]
            # Same-priority contradictory proposals are a hard conflict rather
            # than order-dependent behavior.
            top=rank.get(str(winner['source']),0)
            peers=[row for row in ordered if rank.get(str(row['source']),0)==top]
            deltas={int(row['delta']) for row in peers}
            if len(deltas)>1:
                conflicts.append({'event_key':list(key),'dimension':dim,'sources':[row['source'] for row in peers],'deltas':sorted(deltas)})
                rejected.extend([{**row,'rejection_reason':'same_priority_conflict'} for row in peers]);continue
            winner={**winner,'arbitration':'ACCEPTED','candidate_count':len(candidates)}
            accepted.append(winner)
            for loser in ordered[1:]:
                rejected.append({**loser,'rejection_reason':'lower_priority_proposal'})
    return {
        'schema':'PA800_EVENT_PROPOSAL_ARBITER_V1',
        'proposals_total':len(proposals or []),'accepted':accepted,'rejected':rejected,
        'accepted_count':len(accepted),'rejected_count':len(rejected),'conflicts':conflicts,
        'pass':not conflicts,
    }


def commit_event_proposals(mid, arbitration, report):
    """Atomically apply accepted velocity/onset/duration proposals to *mid*."""
    if not arbitration.get('pass'):
        raise ValueError('Cannot commit conflicted proposal arbitration')
    accepted=arbitration.get('accepted',[]) or []
    by_key=defaultdict(dict)
    for row in accepted:
        by_key[tuple(row['event_key'])][str(row['dimension'])]=row
    current=extract_notes(mid)
    current_by_key={_key(note):note for note in current}
    track_abs={}
    changes=[]
    for key,dims in sorted(by_key.items()):
        note=current_by_key.get(key)
        if note is None:
            raise ValueError('Proposal target disappeared before commit: %r'%(key,))
        if note.track_index not in track_abs:
            track_abs[note.track_index]=absolute_track(mid.tracks[note.track_index])
        events=track_abs[note.track_index]
        final_on=int(note.onset)
        final_duration=int(note.duration)
        vel=dims.get('velocity')
        timing=dims.get('timing')
        gate=dims.get('gate')
        if vel:
            msg=events[note.on_index][2]
            old=int(msg.velocity);new=max(1,min(127,int(vel['new_velocity'])))
            if new!=old:
                events[note.on_index][2]=msg.copy(velocity=new)
                changes.append(Change(note.track_index,note.on_index,str(vel.get('final_change_kind') or 'velocity'),old,new,
                    'proposal_commit:'+str(vel['source']),str(vel.get('reasons') or ''),channel=note.channel,note=note.note,occurrence=note.occurrence,protected=note.protected))
        if timing:
            final_on=max(0,int(note.onset)+int(timing['delta']))
        if gate:
            final_duration=max(1,int(note.duration)+int(gate['delta']))
        # Timing shift preserves duration unless a gate proposal wins.
        final_off=final_on+final_duration
        if timing and final_on!=note.onset:
            events[note.on_index][0]=final_on
            # Move note-off with onset first; gate composition may then change duration.
            events[note.off_index][0]=final_off
            changes.append(Change(note.track_index,note.on_index,'timing',note.onset,final_on,
                'proposal_commit:'+str(timing['source']),str(timing.get('reasons') or ''),channel=note.channel,note=note.note,occurrence=note.occurrence,protected=note.protected))
        if gate and final_off!=note.off+(int(timing['delta']) if timing else 0):
            old_duration=note.duration
            events[note.off_index][0]=final_off
            gate_old_off=note.off+(int(timing['delta']) if timing else 0)
            changes.append(Change(note.track_index,note.off_index,'gate',gate_old_off,final_off,
                'proposal_commit:'+str(gate['source']),str(gate.get('reasons') or ''),channel=note.channel,note=note.note,occurrence=note.occurrence,protected=note.protected))
    for ti,events in track_abs.items():
        mid.tracks[ti]=rebuild_track(events)
    report.changes.extend(changes)
    return {'schema':'PA800_EVENT_PROPOSAL_COMMIT_V1','accepted':len(accepted),'changes_committed':len(changes),'tracks_touched':len(track_abs),'pass':True}



def _controller_snapshot(mid, controls=(11,)):
    rows={}
    for ti,track in enumerate(mid.tracks):
        counts=defaultdict(int)
        tick=0
        for index,msg in enumerate(track):
            tick+=int(getattr(msg,'time',0) or 0)
            if msg.type!='control_change' or int(msg.control) not in controls:
                continue
            ch=int(msg.channel); control=int(msg.control); occ=counts[(ch,control)];counts[(ch,control)]+=1
            rows[(ti,ch,control,occ)]={'track':ti,'channel':ch,'control':control,'occurrence':occ,'index':index,'tick':tick,'value':int(msg.value)}
    return rows


def generate_refiner_proposals(mid, notes, contexts, profiles, registry, musical_context, config):
    """Run Conductor -> Performance Director -> BAJA stage in one sandbox.

    The production MIDI is never mutated here.  The final sandbox state is
    converted to one velocity proposal per event, preserving the full source
    provenance chain. Existing CC11 edits are emitted as controller proposals.
    """
    sandbox=copy.deepcopy(mid)
    sandbox_notes=extract_notes(sandbox)
    classify_intents(sandbox_notes,contexts,sandbox.ticks_per_beat)
    _copy_note_semantics(notes,sandbox_notes)
    before_notes=copy.deepcopy(sandbox_notes)
    before_cc=_controller_snapshot(sandbox,(11,))
    temp=_temp_report()
    normalize_velocity(sandbox,sandbox_notes,contexts,profiles,registry,config,temp)
    # Re-extract because the conductor mutates note velocity in-place and the
    # performance director must see the conductor result, matching legacy order.
    sandbox_notes=extract_notes(sandbox);classify_intents(sandbox_notes,contexts,sandbox.ticks_per_beat)
    _copy_note_semantics(notes,sandbox_notes)
    run_performance_director(sandbox,sandbox_notes,contexts,musical_context,config,temp)
    sandbox_notes=extract_notes(sandbox);classify_intents(sandbox_notes,contexts,sandbox.ticks_per_beat)
    _copy_note_semantics(notes,sandbox_notes)
    stage_changes=0
    if bool(getattr(config,'apply_baja_stage_profile',False)):
        stage_changes=apply_percussion_40_percent(sandbox,sandbox_notes,contexts,temp)
    after_notes=extract_notes(sandbox);classify_intents(after_notes,contexts,sandbox.ticks_per_beat)
    velocity_rows=_proposal_rows(before_notes,after_notes,'velocity','PERFORMANCE_REFINER_PIPELINE',temp)
    after_cc=_controller_snapshot(sandbox,(11,))
    controller_rows=[]
    for key,old in sorted(before_cc.items()):
        new=after_cc.get(key)
        if new is None or int(new['value'])==int(old['value']):
            continue
        controller_rows.append({
            'event_key':list(key),'track':key[0],'channel':key[1],'control':key[2],'occurrence':key[3],
            'source':'PERFORMANCE_DIRECTOR_EXPRESSION','dimension':'controller','old_value':old['value'],'new_value':new['value'],
            'delta':int(new['value'])-int(old['value']),'tick':old['tick']
        })
    return velocity_rows,controller_rows,{
        'schema':'PA800_REFINER_PROPOSAL_GENERATION_V1','source':'PERFORMANCE_REFINER_PIPELINE',
        'velocity_proposals':len(velocity_rows),'controller_proposals':len(controller_rows),
        'sandbox_changes':len(temp.changes),'stage_changes':stage_changes,
        'velocity_conductor':copy.deepcopy(temp.velocity_conductor),
        'performance_director':copy.deepcopy(temp.performance_director),
        'production_midi_mutated':False,
    }


def arbitrate_controller_proposals(proposals):
    grouped=defaultdict(list);accepted=[];rejected=[];conflicts=[]
    for row in proposals or []:
        grouped[tuple(row['event_key'])].append(row)
    for key,candidates in sorted(grouped.items()):
        values={int(row['new_value']) for row in candidates}
        if len(values)>1:
            conflicts.append({'event_key':list(key),'values':sorted(values),'sources':[r['source'] for r in candidates]})
            rejected.extend([{**row,'rejection_reason':'controller_conflict'} for row in candidates]);continue
        winner=sorted(candidates,key=lambda row:str(row['source']))[0]
        accepted.append({**winner,'arbitration':'ACCEPTED','candidate_count':len(candidates)})
        rejected.extend([{**row,'rejection_reason':'duplicate_controller_proposal'} for row in candidates[1:]])
    return {'schema':'PA800_CONTROLLER_PROPOSAL_ARBITER_V1','accepted':accepted,'rejected':rejected,'conflicts':conflicts,
            'accepted_count':len(accepted),'rejected_count':len(rejected),'pass':not conflicts}


def commit_controller_proposals(mid, arbitration):
    if not arbitration.get('pass'):
        raise ValueError('Cannot commit conflicted controller proposals')
    controls=tuple(sorted({int(row.get('control',11)) for row in (arbitration.get('accepted',[]) or [])})) or (11,)
    snapshot=_controller_snapshot(mid,controls);mutations=[]
    for row in arbitration.get('accepted',[]) or []:
        key=tuple(row['event_key']);current=snapshot.get(key)
        if current is None:
            raise ValueError('Controller proposal target disappeared before commit: %r'%(key,))
        msg=mid.tracks[key[0]][current['index']]
        old=int(msg.value);new=max(0,min(127,int(row['new_value'])))
        if new==old:continue
        mid.tracks[key[0]][current['index']]=msg.copy(value=new)
        mutations.append({'track':key[0],'channel':key[1],'control':key[2],'occurrence':key[3],
                          'tick':current['tick'],'old':old,'new':new,'source':'proposal_commit:'+str(row['source'])})
    return {'schema':'PA800_CONTROLLER_PROPOSAL_COMMIT_V1','changes_committed':len(mutations),'mutations':mutations,'pass':True}


def generate_velocity_budget_proposals(mid, notes, contexts, baseline):
    """Create cumulative-original velocity clamp proposals without mutating MIDI."""
    rows=[];by_family=defaultdict(int)
    baseline_notes=(baseline.get('notes') or {}) if isinstance(baseline,dict) else {}
    for note in notes or []:
        key=_key(note);original=baseline_notes.get(key)
        if original is None or bool(note.protected):
            continue
        ctx=contexts.get((note.track_index,note.channel))
        family=policy_for(ctx.family if ctx else 'UNKNOWN').get('policy_family','UNKNOWN')
        cap=int(FAMILY_CUMULATIVE_VELOCITY_CAP.get(family,16))
        origin=int(original['velocity'])
        bounded=max(1,min(127,max(origin-cap,min(origin+cap,int(note.velocity)))))
        if bounded==int(note.velocity):
            continue
        rows.append({
            'event_key':list(key),'track':note.track_index,'channel':note.channel,'note':note.note,
            'occurrence':note.occurrence,'on_index':note.on_index,'off_index':note.off_index,
            'source':'CUMULATIVE_VELOCITY_BUDGET','dimension':'velocity','protected':bool(note.protected),
            'old_velocity':int(note.velocity),'new_velocity':int(bounded),'old_onset':int(note.onset),
            'new_onset':int(note.onset),'old_duration':int(note.duration),'new_duration':int(note.duration),
            'delta':int(bounded)-int(note.velocity),'final_change_kind':'velocity_budget',
            'change_kinds':['velocity_budget'],
            'reasons':[{'kind':'velocity_budget','reason':'cumulative_original_velocity_budget','profile':ctx.identity.name if ctx else family}],
            'family':family,'cap':cap,'original_velocity':origin,
        })
        by_family[family]+=1
    return rows,{
        'schema':'PA800_CUMULATIVE_VELOCITY_BUDGET_PROPOSALS_V1','proposals':len(rows),
        'by_family':dict(sorted(by_family.items())),'family_caps':dict(sorted(FAMILY_CUMULATIVE_VELOCITY_CAP.items())),
        'production_midi_mutated':False,'pass':True,
    }


def generate_mix_fx_proposals(mid, contexts, musical_context, recommendations, config):
    """Run Mix FX Director in a sandbox and emit CC91/CC93 proposals only."""
    sandbox=copy.deepcopy(mid)
    result,authorized,updates=run_mix_fx_director(sandbox,contexts,musical_context,recommendations,config)
    rows=[]
    for mutation in result.get('event_mutations',[]) or []:
        rows.append({
            'event_key':[int(mutation['track']),int(mutation['channel']),int(mutation['control']),int(mutation['occurrence'])],
            'track':int(mutation['track']),'channel':int(mutation['channel']),'control':int(mutation['control']),
            'occurrence':int(mutation['occurrence']),'source':'MIX_FX_DIRECTOR','dimension':'controller',
            'old_value':int(mutation['old']),'new_value':int(mutation['new']),
            'delta':int(mutation['new'])-int(mutation['old']),'tick':int(mutation.get('tick',0)),
        })
    # The audit is preserved, but the production-mutation count is represented
    # as proposals until central commit.
    result=copy.deepcopy(result)
    result['proposal_mode']=True;result['production_midi_mutated']=False
    result['proposal_count']=len(rows)
    return rows,result,authorized,updates


def generate_controller_diff_proposals(before, after, controls=(91,93), source='LEGACY_FX_INTELLIGENCE'):
    """Diff existing controller events between two MIDI states without authorizing insertions."""
    controls=tuple(int(x) for x in controls)
    a=_controller_snapshot(before,controls);b=_controller_snapshot(after,controls);rows=[]
    for key,old in sorted(a.items()):
        new=b.get(key)
        if new is None or int(new['value'])==int(old['value']):continue
        rows.append({'event_key':list(key),'track':key[0],'channel':key[1],'control':key[2],'occurrence':key[3],
            'source':source,'dimension':'controller','old_value':int(old['value']),'new_value':int(new['value']),
            'delta':int(new['value'])-int(old['value']),'tick':int(old['tick'])})
    return rows,{'schema':'PA800_CONTROLLER_DIFF_PROPOSALS_V1','controls':list(controls),'source':source,'proposals':len(rows),'production_midi_mutated':False,'pass':True}
