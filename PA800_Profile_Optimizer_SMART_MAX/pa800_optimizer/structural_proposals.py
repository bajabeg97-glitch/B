"""Structural proposal transactions for voice addresses and inserted articulation events.

Unlike ordinary event proposals, these mutations can alter several related MIDI
messages or insert new messages.  They therefore require atomic validation and
commit semantics.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import mido

from .core.midi_io import absolute_track, rebuild_track
from .neural.event_contract import extract_notes
from .midi_doctor import canonical_midi_digest


def clone_midi(mid):
    return deepcopy(mid)


def _address_events(mid):
    rows = defaultdict(lambda: {'msb': [], 'lsb': [], 'program': []})
    for ti, track in enumerate(mid.tracks):
        tick = 0
        occurrence = defaultdict(int)
        for i, msg in enumerate(track):
            tick += int(msg.time)
            ch = getattr(msg, 'channel', None)
            if ch is None:
                continue
            if msg.type == 'control_change' and msg.control in (0, 32):
                kind = 'msb' if msg.control == 0 else 'lsb'
                occ = occurrence[(ch, kind)]; occurrence[(ch, kind)] += 1
                rows[(ti, ch)][kind].append({'index': i, 'tick': tick, 'occurrence': occ, 'value': int(msg.value)})
            elif msg.type == 'program_change':
                occ = occurrence[(ch, 'program')]; occurrence[(ch, 'program')] += 1
                rows[(ti, ch)]['program'].append({'index': i, 'tick': tick, 'occurrence': occ, 'value': int(msg.program)})
    return rows


def build_sound_address_proposals(before, after, source='sound_selector'):
    """Return atomic Bank MSB/LSB/Program proposals from a sandbox diff.

    No new bank/program messages are authorized.  Multiple Program Change
    channels are rejected because they are multi-timbre/ambiguous by contract.
    Repeated bank setup messages are retained as one atomic address transaction.
    """
    a = _address_events(before); b = _address_events(after)
    proposals = []
    for key in sorted(set(a) | set(b)):
        old = a.get(key, {}); new = b.get(key, {})
        if len(old.get('program', [])) != 1 or len(new.get('program', [])) != 1:
            continue
        if not old.get('msb') or not old.get('lsb'):
            continue
        if [x['occurrence'] for x in old['msb']] != [x['occurrence'] for x in new.get('msb', [])]:
            continue
        if [x['occurrence'] for x in old['lsb']] != [x['occurrence'] for x in new.get('lsb', [])]:
            continue
        target = (new['msb'][0]['value'], new['lsb'][0]['value'], new['program'][0]['value'])
        current = (old['msb'][0]['value'], old['lsb'][0]['value'], old['program'][0]['value'])
        changed = current != target or any(x['value'] != target[0] for x in old['msb']) or any(x['value'] != target[1] for x in old['lsb'])
        if not changed:
            continue
        proposals.append({
            'schema': 'PA800_SOUND_ADDRESS_PROPOSAL_V1',
            'track': key[0], 'channel': key[1], 'source': source,
            'old_address': list(current), 'proposed_address': list(target),
            'msb_occurrences': len(old['msb']), 'lsb_occurrences': len(old['lsb']),
            'program_occurrences': 1,
            'atomic': True, 'inserts_events': False,
        })
    return proposals


def arbitrate_sound_address_proposals(proposals, allowed_targets=None):
    allowed_targets = allowed_targets or {}
    accepted, rejected = [], []
    seen = set()
    for p in proposals:
        key = (int(p['track']), int(p['channel']))
        target = tuple(int(x) for x in p['proposed_address'])
        reason = None
        if key in seen:
            reason = 'duplicate_channel_structural_proposal'
        elif key in allowed_targets and tuple(allowed_targets[key]) != target:
            reason = 'target_not_in_authorized_sound_ledger'
        elif not all(0 <= x <= 127 for x in target):
            reason = 'invalid_midi_address_byte'
        elif int(p.get('program_occurrences', 0)) != 1:
            reason = 'ambiguous_program_occurrence_count'
        if reason:
            rejected.append({**p, 'decision': 'REJECT', 'reason': reason})
        else:
            seen.add(key); accepted.append({**p, 'decision': 'ACCEPT', 'reason': 'atomic_existing_address_rewrite'})
    return {'schema': 'PA800_STRUCTURAL_SOUND_ARBITRATION_V1', 'accepted': accepted, 'rejected': rejected, 'pass': not rejected}


def commit_sound_address_proposals(mid, accepted):
    committed = []
    for p in accepted:
        ti, ch = int(p['track']), int(p['channel'])
        msb, lsb, pc = (int(x) for x in p['proposed_address'])
        track = mid.tracks[ti]
        has_pc = sum(1 for m in track if getattr(m, 'channel', None) == ch and m.type == 'program_change')
        has_msb = sum(1 for m in track if getattr(m, 'channel', None) == ch and m.type == 'control_change' and m.control == 0)
        has_lsb = sum(1 for m in track if getattr(m, 'channel', None) == ch and m.type == 'control_change' and m.control == 32)
        if has_pc != 1 or not has_msb or not has_lsb:
            continue
        changed = 0
        for i, msg in enumerate(track):
            if getattr(msg, 'channel', None) != ch:
                continue
            if msg.type == 'control_change' and msg.control == 0 and msg.value != msb:
                track[i] = msg.copy(value=msb); changed += 1
            elif msg.type == 'control_change' and msg.control == 32 and msg.value != lsb:
                track[i] = msg.copy(value=lsb); changed += 1
            elif msg.type == 'program_change' and msg.program != pc:
                track[i] = msg.copy(program=pc); changed += 1
        committed.append({**p, 'committed_events': changed})
    return committed


def build_articulation_insert_proposals(insertions):
    """Group verifier-compatible insertion tuples into atomic 127/0 pulse pairs."""
    grouped = defaultdict(dict)
    for row in insertions or []:
        ti, ch, tick, control, value, note, occurrence = row
        key = (int(ti), int(ch), int(tick), int(control), int(note), int(occurrence))
        grouped[key][int(value)] = tuple(row)
    accepted, rejected = [], []
    for key, values in sorted(grouped.items()):
        proposal = {'schema': 'PA800_ARTICULATION_INSERT_PROPOSAL_V1', 'track': key[0], 'channel': key[1], 'tick': key[2], 'control': key[3], 'note': key[4], 'occurrence': key[5], 'values': sorted(values), 'atomic': True}
        if set(values) != {0, 127} or key[3] not in (80, 81):
            rejected.append({**proposal, 'decision': 'REJECT', 'reason': 'incomplete_or_unsupported_articulation_pulse'})
        else:
            accepted.append({**proposal, 'decision': 'ACCEPT', 'reason': 'complete_dnc_controller_pulse'})
    return {'schema': 'PA800_STRUCTURAL_INSERT_ARBITRATION_V1', 'accepted': accepted, 'rejected': rejected, 'pass': not rejected}


def commit_articulation_insert_proposals(mid, accepted):
    notes = extract_notes(mid)
    note_map = {(n.track_index, n.channel, n.note, n.occurrence, n.onset): n for n in notes}
    by_track = defaultdict(list); verifier_rows = []
    for p in accepted:
        key = (int(p['track']), int(p['channel']), int(p['note']), int(p['occurrence']), int(p['tick']))
        note = note_map.get(key)
        if note is None:
            continue
        by_track[note.track_index].append((note, p))
    for ti, rows in by_track.items():
        events = absolute_track(mid.tracks[ti])
        for note, p in rows:
            control = int(p['control'])
            events.append([note.onset, note.on_index - 0.25, mido.Message('control_change', channel=note.channel, control=control, value=127, time=0)])
            events.append([note.onset, note.on_index + 0.25, mido.Message('control_change', channel=note.channel, control=control, value=0, time=0)])
            verifier_rows.extend([
                (note.track_index, note.channel, note.onset, control, 127, note.note, note.occurrence),
                (note.track_index, note.channel, note.onset, control, 0, note.note, note.occurrence),
            ])
        mid.tracks[ti] = rebuild_track(events)
    return verifier_rows


def verify_sound_transaction_replay(before, after, accepted):
    replay=deepcopy(before);committed=commit_sound_address_proposals(replay,accepted)
    return {'schema':'PA800_STRUCTURAL_SOUND_REPLAY_V1','pass':canonical_midi_digest(replay)==canonical_midi_digest(after),
            'expected_digest':canonical_midi_digest(after),'replay_digest':canonical_midi_digest(replay),'committed':len(committed)}

def verify_articulation_transaction_replay(before, after, accepted):
    replay=deepcopy(before);rows=commit_articulation_insert_proposals(replay,accepted)
    return {'schema':'PA800_STRUCTURAL_ARTICULATION_REPLAY_V1','pass':canonical_midi_digest(replay)==canonical_midi_digest(after),
            'expected_digest':canonical_midi_digest(after),'replay_digest':canonical_midi_digest(replay),'inserted_events':len(rows)}
