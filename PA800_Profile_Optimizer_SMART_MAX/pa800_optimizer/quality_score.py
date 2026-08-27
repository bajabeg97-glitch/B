"""Evidence-based before/after quality metrics without pretending to rate art."""
from __future__ import annotations

from collections import defaultdict
from .core.midi_io import extract_notes


def _velocity_score(notes, contexts, profiles):
    total = 0
    weighted = 0.0
    covered = 0
    by_ctx = defaultdict(list)
    for note in notes:
        by_ctx[(note.track_index, note.channel)].append(note)
    for key, arr in by_ctx.items():
        profile = profiles.get(key)
        velocity = (profile or {}).get('velocity', {}) or {}
        if not velocity:
            continue
        lo = float(velocity.get('p05', velocity.get('working_min', 1)))
        hi = float(velocity.get('p95', velocity.get('working_max', 127)))
        ideal = float(velocity.get('ideal_center', (lo + hi) / 2.0))
        span = max(8.0, hi - lo)
        for note in arr:
            total += 1; covered += 1
            v = float(note.velocity)
            outside = max(0.0, lo - v, v - hi)
            center = min(1.0, abs(v - ideal) / max(12.0, span))
            # Corridor compliance dominates; center proximity is intentionally
            # weak so expressive tails are not punished into flat dynamics.
            weighted += max(0.0, 1.0 - min(1.0, outside / 24.0)) * 0.85 + (1.0 - center) * 0.15
    if not covered:
        return None, 0
    return round(100.0 * weighted / covered, 3), covered


def evidence_quality_snapshot(mid, contexts, profiles):
    notes = extract_notes(mid)
    vel, covered = _velocity_score(notes, contexts, profiles)
    total = len(notes)
    profile_contexts = sum(1 for key in contexts if profiles.get(key))
    coverage = profile_contexts / max(1, len(contexts))
    return {
        'schema': 'PA800_EVIDENCE_QUALITY_SNAPSHOT_V1',
        'note_count': total,
        'profile_context_coverage': round(coverage, 4),
        'velocity_factory_corridor_score': vel,
        'velocity_scored_notes': covered,
        'artistic_quality_claimed': False,
    }


def compare_quality(before, after):
    b = before.get('velocity_factory_corridor_score')
    a = after.get('velocity_factory_corridor_score')
    delta = None if b is None or a is None else round(float(a) - float(b), 3)
    return {
        'schema': 'PA800_EVIDENCE_QUALITY_DELTA_V1',
        'before': before, 'after': after,
        'velocity_factory_corridor_delta': delta,
        'regression': bool(delta is not None and delta < -5.0),
        'interpretation': 'evidence_metric_only_not_subjective_musical_rating',
    }
