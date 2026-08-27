"""Manual-driven DNC state analysis for Korg Pa800.

Read-only.  It distinguishes:
- SC1 / SC2 => CC80 / CC81 (assignable DNC controllers),
- Joystick Y+ / Y- => CC1 / CC2 with threshold 64,
- Channel Aftertouch trigger threshold 90,
- Damper => CC64,
- legato/staccato candidates from note gap + interval.

Exact oscillator mappings remain Sound-specific and are never guessed.
"""
from __future__ import annotations
from collections import defaultdict
from typing import Dict, Tuple, Any
from ..core.midi_io import absolute_track


def tempo_events(mid):
    ev=[(0,500000)]
    for tr in mid.tracks:
        for at,_idx,msg in absolute_track(tr):
            if msg.type=='set_tempo': ev.append((at,int(msg.tempo)))
    return sorted(set(ev),key=lambda x:x[0])


def ticks_to_ms(delta_ticks:int, at_tick:int, ppq:int, tempos):
    if delta_ticks is None:return None
    # Gap windows relevant to DNC are tiny; use tempo active at current onset.
    tempo=500000
    for t,v in tempos:
        if t<=at_tick: tempo=v
        else: break
    return float(delta_ticks)*tempo/float(ppq)/1000.0


def build_controller_states(mid):
    """Map (track,event_index) Note-On -> controller state immediately before Note-On."""
    out={}
    for ti,tr in enumerate(mid.tracks):
        # MIDI channel voice state is channel-scoped.  A type-0/multi-channel
        # track must never leak CC, aftertouch or pitch-bend state from one
        # channel into a Note-On on another channel.
        states=defaultdict(lambda:defaultdict(int))
        for at,idx,msg in absolute_track(tr):
            ch=getattr(msg,'channel',None)
            if ch is None:
                continue
            state=states[ch]
            if msg.type=='control_change':
                if msg.control in (1,2,64,80,81): state[f'cc{msg.control}']=int(msg.value)
            elif msg.type=='aftertouch':
                state['aftertouch']=int(msg.value)
            elif msg.type=='pitchwheel':
                state['pitchbend']=int(msg.pitch)
            elif msg.type=='note_on' and msg.velocity>0:
                out[(ti,idx)]={k:int(state.get(k,0)) for k in ('cc1','cc2','cc64','cc80','cc81','aftertouch','pitchbend')}
    return out


def evaluate_dnc_note(note, ctx, manual_profile, controller_state, prev_note, ppq, tempos):
    if not manual_profile:
        return {'is_dnc':False}
    caps=set(manual_profile.get('capabilities',[]))
    st=dict(controller_state or {})
    gap_ticks=None; interval=None; gap_ms=None
    if prev_note is not None:
        gap_ticks=note.onset-prev_note.off
        interval=abs(note.note-prev_note.note)
        gap_ms=ticks_to_ms(gap_ticks,note.onset,ppq,tempos)
    generic_legato_15 = bool(prev_note is not None and gap_ms is not None and gap_ms <= 15 and gap_ms >= -1000)
    max_range=(manual_profile.get('legato') or {}).get('max_range_example_semitones')
    if max_range is not None and interval is not None:
        generic_legato_15 = generic_legato_15 and interval <= max_range
    active=[]
    if 'sc1' in caps and st.get('cc80',0)>0: active.append('SC1_CC80')
    if 'sc2' in caps and st.get('cc81',0)>0: active.append('SC2_CC81')
    if 'joystick_y_plus' in caps and st.get('cc1',0)>=64: active.append('JOY_Y_PLUS_CC1')
    if 'joystick_y_minus' in caps and st.get('cc2',0)>=64: active.append('JOY_Y_MINUS_CC2')
    if 'damper' in caps or 'damper_trigger' in caps or 'resonance_halo' in caps:
        if st.get('cc64',0)>=64: active.append('DAMPER_CC64')
    if 'aftertouch' in caps and st.get('aftertouch',0)>=90: active.append('AFTERTOUCH_GE90')
    if 'legato' in caps and generic_legato_15: active.append('LEGATO_CANDIDATE')
    if 'staccato' in caps and prev_note is not None and not generic_legato_15: active.append('STACCATO_CANDIDATE')
    velocity_rules=[]
    arts=manual_profile.get('articulations',{})
    if 'velocity_condition' in caps:
        velocity_rules.append(arts.get('velocity_condition'))
    return {
      'is_dnc':True,
      'manual_name':manual_profile['name'],
      'address':[manual_profile['msb'],manual_profile['lsb'],manual_profile['program']],
      'capabilities':sorted(caps),
      'articulations':arts,
      'controller_state':st,
      'active_candidates':active,
      'gap_ticks_from_previous_note':gap_ticks,
      'gap_ms_from_previous_note':round(gap_ms,4) if gap_ms is not None else None,
      'interval_from_previous_note':interval,
      'legato_candidate_using_15ms_example':generic_legato_15 if 'legato' in caps else None,
      'legato_max_range_example':max_range,
      'velocity_condition_rules':velocity_rules,
      'warning':'15ms is a manual example, not a universal per-Sound Max Time' if 'legato' in caps else None,
    }