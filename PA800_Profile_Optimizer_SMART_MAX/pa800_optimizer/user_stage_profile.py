"""User-authorized stage defaults for the explicit FACTORY + GOLD MAX button.

These rules are deliberately isolated from normal/autopilot modes. They only
run when the user explicitly chooses the MAX button, so Factory/Gold/neural
learning remains unchanged and no retraining is required.
"""
from __future__ import annotations

from .models import Change

BAJA_STAGE_DEFAULTS = {
    'DRUM': {'address': (120, 0, 4), 'label': 'Pop Std. Kit RX'},
    'BASS': {'address': (121, 16, 33), 'label': 'Finger Bass DNC'},
    'RHYTHM_GUITAR': {'address': (121, 35, 25), 'label': 'Rhythm Guitar DNC'},
}


def _presence(track, channel):
    has0 = has32 = haspc = 0
    for msg in track:
        if getattr(msg, 'channel', None) != channel:
            continue
        if msg.type == 'control_change' and msg.control == 0:
            has0 += 1
        elif msg.type == 'control_change' and msg.control == 32:
            has32 += 1
        elif msg.type == 'program_change':
            haspc += 1
    return has0, has32, haspc


def _target_for_context(ctx):
    role = str(getattr(ctx, 'role', '') or '').upper()
    channel = int(getattr(ctx, 'channel', -1))
    if role == 'DRUM' or channel == 9:
        return 'DRUM', BAJA_STAGE_DEFAULTS['DRUM']
    if role == 'BASS' or channel == 8:
        return 'BASS', BAJA_STAGE_DEFAULTS['BASS']
    # Pa800/StyleWorks project convention: MIDI CH12 (zero-based 11) is rhythm guitar.
    if channel == 11 or role == 'ACC1':
        return 'RHYTHM_GUITAR', BAJA_STAGE_DEFAULTS['RHYTHM_GUITAR']
    return None, None


def apply_stage_sound_defaults(mid, contexts):
    """Rewrite existing Bank/Program events only; never invent structure."""
    changed_targets = {}
    rows = []
    for key, ctx in sorted(contexts.items()):
        kind, spec = _target_for_context(ctx)
        if not spec:
            continue
        track = mid.tracks[int(ctx.track_index)]
        ch = int(ctx.channel)
        has0, has32, haspc = _presence(track, ch)
        if not (has0 and has32 and haspc):
            rows.append({'track': ctx.track_index, 'channel': ch + 1, 'role': kind,
                         'target': list(spec['address']), 'label': spec['label'],
                         'status': 'blocked_missing_existing_bank_or_program'})
            continue
        if haspc != 1:
            rows.append({'track': ctx.track_index, 'channel': ch + 1, 'role': kind,
                         'target': list(spec['address']), 'label': spec['label'],
                         'status': 'blocked_multiple_program_events'})
            continue
        msb, lsb, pc = spec['address']
        changed = False
        for i, msg in enumerate(track):
            if getattr(msg, 'channel', None) != ch:
                continue
            if msg.type == 'control_change' and msg.control == 0 and msg.value != msb:
                track[i] = msg.copy(value=msb); changed = True
            elif msg.type == 'control_change' and msg.control == 32 and msg.value != lsb:
                track[i] = msg.copy(value=lsb); changed = True
            elif msg.type == 'program_change' and msg.program != pc:
                track[i] = msg.copy(program=pc); changed = True
        changed_targets[(int(ctx.track_index), ch)] = tuple(spec['address'])
        rows.append({'track': ctx.track_index, 'channel': ch + 1, 'role': kind,
                     'target': list(spec['address']), 'label': spec['label'],
                     'status': 'applied' if changed else 'already_target'})
    return changed_targets, rows


def apply_percussion_40_percent(mid, notes, contexts, report):
    """Final explicit stage mix rule: PERC/Conga/etc. velocity becomes 40%.

    Applied after profile normalization so earlier engines cannot turn it back up.
    Protected RX/DNC notes are preserved.
    """
    changed = 0
    for note in notes:
        ctx = contexts.get((note.track_index, note.channel))
        if not ctx or note.protected:
            continue
        role = str(getattr(ctx, 'role', '') or '').upper()
        # Dedicated PERC track/channel only; do not attenuate the main DRUM kit.
        if role != 'PERC' and note.channel != 10:
            continue
        old = int(note.velocity)
        new = max(1, min(127, int(round(old * 0.40))))
        if new == old:
            continue
        mid.tracks[note.track_index][note.on_index] = mid.tracks[note.track_index][note.on_index].copy(velocity=new)
        note.velocity = new
        report.changes.append(Change(note.track_index, note.on_index, 'baja_percussion_40pct', old, new,
                                     'explicit_user_stage_mix_percussion_40_percent',
                                     getattr(ctx.identity, 'name', None) or 'PERC', channel=note.channel,
                                     note=note.note, occurrence=note.occurrence, protected=False))
        changed += 1
    return changed
