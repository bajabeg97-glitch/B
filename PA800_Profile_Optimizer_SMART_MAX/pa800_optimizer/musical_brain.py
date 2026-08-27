"""Evidence-driven musical decision planning for autonomous optimization.

This layer does not invent musical facts.  It converts already-computed
Factory/context/intent evidence into an explicit, inspectable plan that can be
consumed by mutation engines and audited after the run.
"""
from __future__ import annotations

from collections import Counter

from .premium_control import context_ood_status, mutation_budget_for, scale_mutation_budget

_EVIDENCE_SCORE = {'E0': 0.0, 'E1': 0.34, 'E2': 0.67, 'E3': 1.0}


def _support_confidence(profile):
    if not profile:
        return 0.0
    support = profile.get('support', {}) or {}
    grade = str(support.get('grade', 'UNKNOWN')).upper()
    base = {'STRONG': 1.0, 'GOOD': 0.82, 'WEAK': 0.45, 'LOW': 0.25}.get(grade, 0.25)
    styles = max(0, int(support.get('styles', 0) or 0))
    notes = max(0, int(support.get('notes', 0) or 0))
    diversity = min(1.0, styles / 8.0)
    volume = min(1.0, notes / 1000.0)
    return round(min(1.0, base * 0.65 + diversity * 0.20 + volume * 0.15), 4)


def build_musical_decision_plan(contexts, profiles, instrument_intent=None, *, notes=None, song_map=None, phrase_doctor=None, preserve_keys=frozenset(), user_stage=False, ticks_per_beat=192):
    """Build one deterministic per-track/channel plan.

    The plan is deliberately conservative: unknown/conflicting contexts are
    PRESERVE; strong evidence permits deeper correction, but never authorizes
    pitch/harmony mutation.  User stage policy is recorded as a separate
    authority rather than silently folded into model confidence.
    """
    intent_rows = {}
    for row in (instrument_intent or {}).get('track_intents', []) or []:
        try:
            intent_rows[(int(row.get('track')), int(row.get('channel')) - 1)] = row
        except (TypeError, ValueError):
            continue
    note_rows = {}
    for note in (notes or []):
        note_rows.setdefault((note.track_index,note.channel),[]).append(note)
    rows = []
    counts = Counter()
    for key in sorted(contexts):
        ctx = contexts[key]
        profile = profiles.get(key)
        evidence = str(getattr(ctx, 'resolution_status', '') or '')
        # Context evidence is intentionally inferred only from already-resolved
        # identity/profile state, not from filename or genre guesses.
        if getattr(ctx.identity, 'conflict', False) or profile is None:
            level = 'E0'
        else:
            grade = str((profile.get('support', {}) or {}).get('grade', '')).upper()
            level = 'E3' if grade == 'STRONG' else 'E2' if grade == 'GOOD' else 'E1'
        support_conf = _support_confidence(profile)
        intent = intent_rows.get(key, {})
        intent_conf = float(intent.get('confidence', 0.0) or 0.0)
        unknown_intent = str(intent.get('label', '')).upper() == 'UNKNOWN'
        ood_status = context_ood_status(ctx, profile, intent_conf)
        register_ood_fraction = 0.0
        key_profile = (profile or {}).get('key', {}) or {}
        local_notes = note_rows.get(key, [])
        try:
            raw_min=float(key_profile.get('raw_min')); raw_max=float(key_profile.get('raw_max'))
            if local_notes:
                outside=sum(1 for note in local_notes if float(note.note)<raw_min or float(note.note)>raw_max)
                register_ood_fraction=round(outside/float(len(local_notes)),4)
                if register_ood_fraction>=0.50 and ood_status=='NORMAL':
                    ood_status='OOD'
                elif register_ood_fraction>0.0 and ood_status=='NORMAL':
                    ood_status='LOW_SUPPORT'
        except (TypeError,ValueError):
            register_ood_fraction=0.0
        hard_preserve = key in preserve_keys or ood_status == 'HARD_PRESERVE' or (unknown_intent and level == 'E0')
        combined = round(0.65 * _EVIDENCE_SCORE[level] + 0.25 * support_conf + 0.10 * max(0.0, min(1.0, intent_conf)), 4)
        if combined >= .82: confidence_band='VERY_HIGH'
        elif combined >= .62: confidence_band='HIGH'
        elif combined >= .42: confidence_band='MEDIUM'
        else: confidence_band='LOW'
        if hard_preserve:
            action, strength, risk = 'PRESERVE', 0.0, 'HIGH'
        elif combined >= 0.82:
            action, strength, risk = 'STRONG_CORRECT', 1.0, 'LOW'
        elif combined >= 0.62:
            action, strength, risk = 'NORMAL_CORRECT', 0.72, 'LOW'
        elif combined >= 0.42:
            action, strength, risk = 'LIGHT_CORRECT', 0.38, 'MEDIUM'
        else:
            action, strength, risk = 'PRESERVE', 0.0, 'HIGH'
        budget = mutation_budget_for(ctx, action, strength, ticks_per_beat)
        # Section/phrase scopes may only tighten the track budget. They never
        # grant mutation authority. Inferred sections and phrase anomalies are
        # deliberately more conservative until musician/ground-truth evidence
        # promotes them.
        section_budgets=[]
        for section in (song_map or {}).get('sections', []) or []:
            level=str(section.get('evidence_level','E0')).upper()
            factor=1.0 if level in ('E2','E3') else 0.75 if level=='E1' else 0.50
            scoped=scale_mutation_budget(budget,factor)
            # Velocity normalization/technique shaping already has a mature
            # track-level Factory budget. Section confidence only tightens the
            # time-domain dimensions so it cannot defeat the conductor.
            scoped['velocity_delta']=int(budget.get('velocity_delta',0) or 0)
            section_budgets.append({
                'section_index':section.get('index'), 'label':section.get('label','UNKNOWN'),
                'start_tick':int(section.get('start_tick',0) or 0), 'end_tick':int(section.get('end_tick',0) or 0),
                'evidence_level':level, 'factor':factor, 'scope_dimensions':['timing','gate'],
                'mutation_budget':scoped,
            })
        findings_by_phrase=Counter(str(row.get('phrase_id')) for row in (phrase_doctor or {}).get('findings',[]) or [])
        phrase_budgets=[]
        for phrase in (song_map or {}).get('phrases', []) or []:
            if int(phrase.get('track',-1)) != int(ctx.track_index) or int(phrase.get('channel',0))-1 != int(ctx.channel):
                continue
            findings=int(findings_by_phrase.get(str(phrase.get('id')),0))
            factor=0.50 if findings else 0.75
            scoped=scale_mutation_budget(budget,factor)
            scoped['velocity_delta']=int(budget.get('velocity_delta',0) or 0)
            phrase_budgets.append({
                'phrase_id':phrase.get('id'), 'section_index':phrase.get('section_index'),
                'start_tick':int(phrase.get('start_tick',0) or 0), 'end_tick':int(phrase.get('end_tick',0) or 0),
                'findings':findings, 'factor':factor, 'scope_dimensions':['timing','gate'],
                'mutation_budget':scoped,
            })
        counts[action] += 1
        rows.append({
            'track': int(ctx.track_index), 'channel': int(ctx.channel) + 1,
            'role': ctx.role, 'family': ctx.family, 'sound': ctx.identity.name,
            'address': list(ctx.identity.address()), 'evidence_level': level,
            'resolution_status': evidence, 'support_confidence': support_conf,
            'intent_confidence': round(intent_conf, 4), 'combined_confidence': combined,
            'risk': risk, 'action': action, 'strength_cap': strength,
            'ood_status': ood_status, 'register_ood_fraction': register_ood_fraction,
            'confidence_band': confidence_band, 'confidence_calibrated': False,
            'confidence_calibration_status': 'CORPUS_SUPPORT_BANDED_NOT_ACCURACY_CALIBRATED',
            'confidence_semantics': 'evidence_support_score_not_probability',
            'mutation_budget': budget,
            'section_mutation_budgets': section_budgets,
            'phrase_mutation_budgets': phrase_budgets,
            'pitch_harmony_authority': False,
            'user_stage_authority': bool(user_stage),
            'reason': 'conflict_or_unknown_preserve' if hard_preserve else 'evidence_weighted_minimal_change',
        })
    return {
        'schema': 'PA800_MUSICAL_DECISION_PLAN_V3',
        'authority': 'PLAN_ONLY_BOUNDED_BY_EXISTING_FACTORY_GOLD_RX_DNC_RULES',
        'tracks': rows,
        'summary': {'contexts': len(rows), 'actions': dict(sorted(counts.items())), 'preserve': counts.get('PRESERVE', 0)},
        'pass': True,
    }
