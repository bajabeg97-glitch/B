"""Premium autonomous safety controls.

This module deliberately keeps *authority* separate from *compute*.  It does
not invent musical edits.  It evaluates whether the already-authorized
performance pass stayed inside explicit per-context budgets and records
self-healing / rollback decisions in machine-readable form.
"""
from __future__ import annotations

from collections import Counter

from .instruments.policies import FAMILY_CUMULATIVE_VELOCITY_CAP, policy_for
from .instruments.guards import note_id
from .core.midi_io import absolute_track, rebuild_track, extract_notes
from .models import Change


def context_ood_status(ctx, profile, intent_confidence=0.0):
    """Conservative support/OOD classification; confidence is not a probability."""
    if ctx is None or getattr(getattr(ctx, 'identity', None), 'conflict', False):
        return 'HARD_PRESERVE'
    if not profile:
        return 'HARD_PRESERVE'
    support = profile.get('support', {}) or {}
    grade = str(support.get('grade', '') or '').upper()
    styles = max(0, int(support.get('styles', 0) or 0))
    notes = max(0, int(support.get('notes', 0) or 0))
    if grade in ('STRONG', 'GOOD') and styles >= 3 and notes >= 100:
        return 'NORMAL'
    if styles <= 1 or notes < 24:
        return 'OOD' if float(intent_confidence or 0.0) < 0.45 else 'LOW_SUPPORT'
    return 'LOW_SUPPORT'


def mutation_budget_for(ctx, action, strength_cap, ticks_per_beat):
    """Upper safety envelope, not a target.  Zero means preserve."""
    family = policy_for(ctx.family if ctx else 'UNKNOWN').get('policy_family', 'UNKNOWN')
    base_velocity = int(FAMILY_CUMULATIVE_VELOCITY_CAP.get(family, 16))
    scale = max(0.0, min(1.0, float(strength_cap or 0.0)))
    if str(action) == 'PRESERVE':
        scale = 0.0
    tpb = max(1, int(ticks_per_beat or 192))
    # Timing is intentionally tighter than gate. These are fail-closed upper
    # envelopes; actual Factory/profile engines usually operate far below them.
    velocity = int(round(base_velocity * scale))
    timing = int(round((tpb / 8.0) * scale))
    gate = int(round((tpb / 2.0) * scale))
    return {
        'velocity_delta': max(0, velocity),
        'timing_delta_ticks': max(0, timing),
        'gate_duration_delta_ticks': max(0, gate),
        'controller_mutations': 0,
        'pitch_mutations': 0,
        'harmony_mutations': 0,
    }




def scale_mutation_budget(budget, factor):
    """Return a stricter copy of a mutation budget; never widens authority."""
    factor=max(0.0,min(1.0,float(factor or 0.0)))
    out={}
    for key,value in (budget or {}).items():
        if isinstance(value,(int,float)):
            out[key]=max(0,int(round(float(value)*factor)))
        else:
            out[key]=value
    return out


def effective_mutation_budget(row, onset):
    """Most restrictive applicable track/section/phrase budget for one note."""
    base=dict((row or {}).get('mutation_budget',{}) or {})
    candidates=[base]
    tick=int(onset or 0)
    for scope_key in ('section_mutation_budgets','phrase_mutation_budgets'):
        for scope in (row or {}).get(scope_key,[]) or []:
            start=int(scope.get('start_tick',0) or 0); end=int(scope.get('end_tick',start) or start)
            if start <= tick < max(start+1,end):
                candidates.append(scope.get('mutation_budget',{}) or {})
    keys=set().union(*(candidate.keys() for candidate in candidates)) if candidates else set()
    out={}
    for key in keys:
        vals=[int(candidate.get(key,0) or 0) for candidate in candidates if key in candidate]
        out[key]=min(vals) if vals else 0
    return out


def audit_performance_budget(before_state, final_notes, decision_plan):
    """Compare final event state to the snapshot before performance shaping."""
    before = (before_state or {}).get('notes', {}) or {}
    plan_rows = {
        (int(row.get('track')), int(row.get('channel')) - 1): row
        for row in (decision_plan or {}).get('tracks', []) or []
    }
    violations = []
    violation_total = 0
    evaluated = 0
    by_dimension = Counter()
    for note in final_notes or []:
        key = note_id(note)
        old = before.get(key)
        if old is None:
            continue
        row = plan_rows.get((note.track_index, note.channel))
        if not row:
            continue
        budget = effective_mutation_budget(row, note.onset)
        evaluated += 1
        velocity_delta = abs(int(note.velocity) - int(old['velocity']))
        timing_delta = abs(int(note.onset) - int(old['onset']))
        old_duration = int(old['off']) - int(old['onset'])
        new_duration = int(note.off) - int(note.onset)
        gate_delta = abs(new_duration - old_duration)
        checks = (
            ('velocity', velocity_delta, int(budget.get('velocity_delta', 0) or 0)),
            ('timing', timing_delta, int(budget.get('timing_delta_ticks', 0) or 0)),
            ('gate', gate_delta, int(budget.get('gate_duration_delta_ticks', 0) or 0)),
        )
        for dimension, delta, cap in checks:
            if delta > cap:
                violation_total += 1
                by_dimension[dimension] += 1
                if len(violations) < 100:
                    violations.append({
                        'note_id': list(key), 'dimension': dimension,
                        'delta': delta, 'cap': cap,
                        'action': row.get('action'), 'risk': row.get('risk'),
                        'ood_status': row.get('ood_status'),
                    })
    return {
        'schema': 'PA800_PREMIUM_MUTATION_BUDGET_AUDIT_V1',
        'notes_evaluated': evaluated,
        'violations': violation_total,
        'violations_by_dimension': dict(sorted(by_dimension.items())),
        'samples': violations[:25],
        'pass': violation_total == 0,
    }


def apply_selective_budget_rollback(mid, before_state, decision_plan):
    """Rollback only dimensions that exceed the explicit per-track budget.

    Velocity is restored on the individual note-on. Timing and gate are restored
    through absolute event positions and the track is rebuilt, preserving valid
    SMF delta-time ordering. This is safer and narrower than reverting the whole
    performance stage.
    """
    before = (before_state or {}).get('notes', {}) or {}
    plan_rows = {
        (int(row.get('track')), int(row.get('channel')) - 1): row
        for row in (decision_plan or {}).get('tracks', []) or []
    }
    notes = extract_notes(mid)
    abs_tracks = {}
    changed_tracks = set()
    rolled = Counter()
    rolled_note_ids = set()
    rolled_event_dimensions = []
    for note in notes:
        nid = note_id(note)
        old = before.get(nid)
        row = plan_rows.get((note.track_index, note.channel))
        if old is None or row is None:
            continue
        budget = effective_mutation_budget(row, note.onset)
        vcap = int(budget.get('velocity_delta', 0) or 0)
        tcap = int(budget.get('timing_delta_ticks', 0) or 0)
        gcap = int(budget.get('gate_duration_delta_ticks', 0) or 0)
        velocity_bad = abs(int(note.velocity) - int(old['velocity'])) > vcap
        timing_bad = abs(int(note.onset) - int(old['onset'])) > tcap
        old_duration = int(old['off']) - int(old['onset'])
        current_duration = int(note.off) - int(note.onset)
        gate_bad = abs(current_duration - old_duration) > gcap
        if not (velocity_bad or timing_bad or gate_bad):
            continue
        if note.track_index not in abs_tracks:
            abs_tracks[note.track_index] = absolute_track(mid.tracks[note.track_index])
        events = abs_tracks[note.track_index]
        by_index = {event[1]: event for event in events}
        if velocity_bad and note.on_index in by_index:
            event = by_index[note.on_index]
            event[2] = event[2].copy(velocity=int(old['velocity']))
            rolled['velocity'] += 1
            rolled_event_dimensions.append({'note_id':list(nid),'dimension':'velocity'})
        new_on = int(old['onset']) if timing_bad else int(note.onset)
        if timing_bad and note.on_index in by_index:
            by_index[note.on_index][0] = new_on
            rolled['timing'] += 1
            rolled_event_dimensions.append({'note_id':list(nid),'dimension':'timing'})
        if note.off_index in by_index and (timing_bad or gate_bad):
            if gate_bad:
                new_off = new_on + old_duration
                rolled['gate'] += 1
                rolled_event_dimensions.append({'note_id':list(nid),'dimension':'gate'})
            else:
                new_off = new_on + current_duration
            by_index[note.off_index][0] = max(new_on + 1, int(new_off))
        changed_tracks.add(note.track_index)
        rolled_note_ids.add(nid)
    for track_index in sorted(changed_tracks):
        mid.tracks[track_index] = rebuild_track(abs_tracks[track_index])
    return {
        'schema': 'PA800_SELECTIVE_BUDGET_ROLLBACK_V1',
        'rolled_dimensions': dict(sorted(rolled.items())),
        'rolled_notes': len(rolled_note_ids),
        'changed_tracks': sorted(changed_tracks),
        'rolled_event_dimensions': rolled_event_dimensions,
        'pass': True,
    }


def recovery_record(*, stage, reason, action, error=None, changes_rolled_back=0):
    return {
        'schema': 'PA800_SELF_HEALING_RECOVERY_V1',
        'stage': str(stage),
        'reason': str(reason),
        'action': str(action),
        'error': None if error is None else '%s: %s' % (type(error).__name__, str(error)[:500]),
        'changes_rolled_back': int(changes_rolled_back),
        'pass': True,
    }


def reconcile_change_ledger_after_selective_rollback(changes, before_state, final_notes, rollback_report):
    """Keep the authorized note-change ledger consistent with rolled MIDI state.

    Selective rollback may undo one dimension after several engines already
    recorded mutations.  The canonical verifier replays that ledger, so stale
    entries must be removed for the rolled dimension.  Unaffected provenance is
    preserved; if a rolled dimension still differs from baseline, one canonical
    reconciled change is emitted.
    """
    affected={(tuple(row.get('note_id',[])),str(row.get('dimension'))) for row in (rollback_report or {}).get('rolled_event_dimensions',[]) or []}
    if not affected:
        return list(changes or [])
    velocity_kinds={'velocity','velocity_conductor','velocity_budget','performance_velocity','baja_percussion_40pct'}
    def family(change):
        kind=str(getattr(change,'kind',''))
        if kind in velocity_kinds:return 'velocity'
        if kind=='timing':return 'timing'
        if kind=='gate':return 'gate'
        return None
    kept=[]
    for change in changes or []:
        if None in (getattr(change,'channel',None),getattr(change,'note',None),getattr(change,'occurrence',None)):
            kept.append(change);continue
        nid=(int(change.track),int(change.channel),int(change.note),int(change.occurrence))
        if (nid,family(change)) in affected:
            continue
        kept.append(change)
    before=(before_state or {}).get('notes',{}) or {}
    final={note_id(note):note for note in final_notes or []}
    for nid,dimension in sorted(affected,key=lambda item:(item[0],item[1])):
        old=before.get(nid);note=final.get(nid)
        if old is None or note is None:continue
        if dimension=='velocity': oldv,newv=int(old['velocity']),int(note.velocity)
        elif dimension=='timing': oldv,newv=int(old['onset']),int(note.onset)
        elif dimension=='gate': oldv,newv=int(old['off']),int(note.off)
        else:continue
        if oldv==newv:continue
        kept.append(Change(track=nid[0],event_index=int(note.on_index),kind=dimension,old=oldv,new=newv,reason='premium_reconciled_after_selective_rollback',channel=nid[1],note=nid[2],occurrence=nid[3],protected=bool(note.protected)))
    return kept
