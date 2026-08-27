"""Detailed per-note velocity/max analysis for PA800 profile-driven workflows.

This module is analysis-only.  It never mutates MIDI data.
It combines:
- exact PA800 Sound identity + role/Element/CV context,
- exact Drum Kit key profiles when available,
- Factory-derived velocity working/ideal/raw zones,
- local musical context and note intent,
- RX/DNC/special-note protection state,
- contextual velocity ceilings (secondary/normal/accent),
- local headroom/outlier/max detection.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
import csv
import json
import math
import statistics

from ..core.midi_io import absolute_track, extract_notes, load_midi
from ..analysis.context import build_contexts, parse_element, parse_cv, role_for, gm_family
from ..analysis.intent import classify_intents
from ..analysis.dnc_state import build_controller_states, tempo_events, evaluate_dnc_note
from ..models import SoundIdentity, TrackContext
from ..profiles.registry import ProfileRegistry
from ..safety.rx_dnc import protect_note, special_pitch
from ..utils import quantiles
from ..config import OptimizeConfig


NOTE_NAMES = ('C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B')


def midi_note_name(note: int) -> str:
    # MIDI 60 = C4
    return '%s%d' % (NOTE_NAMES[note % 12], note // 12 - 1)


def _num(v: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        x = float(v)
        if math.isfinite(x):
            return x
    except Exception:
        pass
    return default


def _iround(v: Any, default: Optional[int] = None) -> Optional[int]:
    x = _num(v, None)
    return int(round(x)) if x is not None else default


def _velocity_limits(profile: Optional[dict]) -> Dict[str, Optional[int]]:
    v = (profile or {}).get('velocity', {}) or {}
    raw_min = _iround(v.get('raw_min'))
    working_min = _iround(v.get('working_min'))
    ideal_min = _iround(v.get('ideal_min'))
    ideal_center = _iround(v.get('ideal_center'))
    ideal_max = _iround(v.get('ideal_max'))
    working_max = _iround(v.get('working_max'))
    p95 = _iround(v.get('p95'))
    p99 = _iround(v.get('p99'))
    raw_max = _iround(v.get('raw_max'))

    # Drum-key profiles do not always have p99. Never invent a value beyond the
    # observed raw maximum; use p95/working max as progressively weaker fallbacks.
    if p95 is None:
        p95 = working_max
    if p99 is None:
        p99 = raw_max

    vals = {
        'raw_min': raw_min,
        'working_min': working_min,
        'ideal_min': ideal_min,
        'ideal_center': ideal_center,
        'ideal_max': ideal_max,
        'working_max': working_max,
        'p95': p95,
        'p99': p99,
        'raw_max': raw_max,
    }
    for k, x in list(vals.items()):
        if x is not None:
            vals[k] = max(1, min(127, int(x)))
    return vals


def _profile_support(profile: Optional[dict]) -> Dict[str, Any]:
    if not profile:
        return {'notes_or_hits': 0, 'styles': 0, 'grade': 'NONE'}
    s = profile.get('support', {}) or {}
    n = int(s.get('notes', s.get('hits', 0)) or 0)
    styles = int(s.get('styles', 0) or 0)
    grade = s.get('grade')
    if not grade:
        if n >= 1000 and styles >= 10:
            grade = 'STRONG'
        elif n >= 300 and styles >= 5:
            grade = 'GOOD'
        elif n >= 100 and styles >= 3:
            grade = 'LIMITED'
        else:
            grade = 'WEAK'
    return {'notes_or_hits': n, 'styles': styles, 'grade': grade}


def _profile_source(ctx, parent: Optional[dict], selected: Optional[dict], drum_key: bool) -> str:
    if selected is None:
        return 'NONE'
    if drum_key:
        return 'EXACT_DRUM_KEY'
    if selected.get('_element_override'):
        return 'EXACT_SOUND_ELEMENT'
    if parent is not None:
        return 'EXACT_SOUND'
    return 'UNKNOWN_PROFILE'


def _zone(velocity: int, lim: Dict[str, Optional[int]]) -> str:
    if lim.get('raw_min') is None:
        return 'NO_PROFILE'
    if velocity < lim['raw_min']:
        return 'BELOW_FACTORY_RAW_MIN'
    if lim.get('working_min') is not None and velocity < lim['working_min']:
        return 'BELOW_WORKING'
    if lim.get('ideal_min') is not None and velocity < lim['ideal_min']:
        return 'WORKING_LOW'
    if lim.get('ideal_max') is not None and velocity <= lim['ideal_max']:
        return 'IDEAL'
    if lim.get('working_max') is not None and velocity <= lim['working_max']:
        return 'WORKING_HIGH'
    if lim.get('p95') is not None and velocity <= lim['p95']:
        return 'ABOVE_WORKING_P95'
    if lim.get('raw_max') is not None and velocity <= lim['raw_max']:
        return 'EXTREME_FACTORY_OBSERVED'
    return 'ABOVE_FACTORY_RAW_MAX'


def _estimated_percentile(velocity: int, lim: Dict[str, Optional[int]]) -> Optional[float]:
    # Profile schema maps the central boundaries approximately to these percentiles.
    pts = [
        (lim.get('raw_min'), 0.0),
        (lim.get('working_min'), 10.0),
        (lim.get('ideal_min'), 25.0),
        (lim.get('ideal_center'), 50.0),
        (lim.get('ideal_max'), 75.0),
        (lim.get('working_max'), 90.0),
        (lim.get('p95'), 95.0),
        (lim.get('p99'), 99.0),
        (lim.get('raw_max'), 100.0),
    ]
    pts = [(float(x), p) for x, p in pts if x is not None]
    if len(pts) < 2:
        return None
    # collapse duplicate x values, keeping the highest percentile at that velocity
    compact = []
    for x, p in sorted(pts):
        if compact and compact[-1][0] == x:
            compact[-1] = (x, max(compact[-1][1], p))
        else:
            compact.append((x, p))
    if velocity <= compact[0][0]:
        return 0.0
    if velocity >= compact[-1][0]:
        return 100.0
    for (x0, p0), (x1, p1) in zip(compact, compact[1:]):
        if x0 <= velocity <= x1:
            if x1 == x0:
                return p1
            t = (velocity - x0) / (x1 - x0)
            return round(p0 + t * (p1 - p0), 2)
    return None


ACCENT_INTENTS = {'METRIC_MAIN', 'METRIC_ANCHOR', 'PHRASE_ACCENT', 'ENSEMBLE_HIT'}
SOFT_INTENTS = {'SECONDARY_HIT', 'PASSING_CANDIDATE', 'APPROACH_CANDIDATE'}


def _contextual_max(intent: str, lim: Dict[str, Optional[int]], protected: bool, velocity: int) -> Tuple[Optional[int], str]:
    if protected:
        return velocity, 'PROTECTED_ORIGINAL'
    if lim.get('working_max') is None:
        return None, 'NO_PROFILE'
    if intent in SOFT_INTENTS:
        return lim.get('ideal_max') or lim.get('working_max'), 'SOFT_IDEAL_MAX'
    if intent in ACCENT_INTENTS:
        # Accent may enter the upper observed band, but not the raw absolute extreme by default.
        return lim.get('p95') or lim.get('working_max') or lim.get('raw_max'), 'ACCENT_P95_MAX'
    if intent in {'REPEATED', 'REPEATED_RIFF', 'CHORD_STRUM'}:
        return lim.get('working_max'), 'WORKING_MAX'
    return lim.get('working_max'), 'WORKING_MAX'


def _action(velocity: int, contextual_max: Optional[int], lim: Dict[str, Optional[int]], protected: bool) -> str:
    if protected:
        return 'PROTECT'
    if contextual_max is None:
        return 'PRESERVE_NO_PROFILE'
    if velocity > contextual_max:
        return 'OVER_CONTEXTUAL_MAX'
    if lim.get('working_min') is not None and velocity < lim['working_min']:
        return 'BELOW_WORKING_REVIEW'
    if velocity == 127:
        return 'MIDI_MAX_127_REVIEW'
    if contextual_max - velocity <= 2:
        return 'AT_CONTEXTUAL_CEILING'
    return 'WITHIN_PROFILE'


def _looks_like_sound_label(text: str) -> bool:
    s=' '.join((text or '').strip().split())
    if not s:
        return False
    if parse_element(s):
        return False
    low=s.lower()
    if low.startswith('sn:') or low.endswith('bar') or low.endswith('bars'):
        return False
    if low.startswith(('variation ', 'intro ', 'fill ', 'ending ', 'break')):
        return False
    return True


def _build_note_event_contexts(mid, registry: ProfileRegistry) -> Dict[Tuple[int,int], TrackContext]:
    """Resolve PA800 context at the exact Note-On event, not once per track.

    StyleWorks/Factory exports concatenate Variation/Intro/Fill/Ending sections in
    one MIDI track.  Bank/program and Sound labels may also change by section.
    The key is (track_index, note_on_event_index).
    """
    out={}
    for ti,tr in enumerate(mid.tracks):
        t=0
        state=defaultdict(lambda: {'msb':None,'lsb':None,'program':None,'sound_label':None})
        current_element=None
        current_cv=None
        current_track_name=''
        for idx,msg in enumerate(tr):
            t += msg.time
            if msg.type=='track_name':
                current_track_name=getattr(msg,'name','') or current_track_name
                cv=parse_cv(getattr(msg,'name',''))
                if cv is not None: current_cv=cv
            elif msg.type in ('text','marker','cue_marker'):
                txt=getattr(msg,'text','') or ''
                el=parse_element(txt)
                if el: current_element=el
                elif _looks_like_sound_label(txt):
                    # The label applies to the channel whose bank/program is being
                    # defined in this section. Keep as a track-level candidate and
                    # copy it to active channel state on the subsequent program.
                    for ch in state:
                        state[ch]['pending_sound_label']=txt.strip()
            if not hasattr(msg,'channel'):
                continue
            st=state[msg.channel]
            if msg.type=='control_change' and msg.control==0:
                st['msb']=msg.value
            elif msg.type=='control_change' and msg.control==32:
                st['lsb']=msg.value
            elif msg.type=='program_change':
                st['program']=msg.program
                if st.get('pending_sound_label'):
                    st['sound_label']=st.pop('pending_sound_label')
            elif msg.type=='note_on' and msg.velocity>0:
                role=role_for(msg.channel,current_track_name)
                prof,status=registry.resolve_identity_with_name(st['msb'],st['lsb'],st['program'],st.get('sound_label'),role)
                manual_dnc=registry.resolve_manual_dnc(st['msb'],st['lsb'],st['program'])
                if prof:
                    ii=prof['identity']; fam=ii.get('org_family','UNKNOWN'); name=ii.get('sound'); rx=ii.get('rx_named',False); dnc=bool(ii.get('dnc_named',False) or manual_dnc)
                    if manual_dnc:
                        name=manual_dnc['name']; fam=manual_dnc.get('family',fam)
                elif manual_dnc:
                    fam=manual_dnc.get('family','UNKNOWN'); name=manual_dnc['name']; rx=False; dnc=True; status='MANUAL_DNC_EXACT'
                else:
                    fam='DRUM_KIT' if role in ('DRUM','PERC') else gm_family(st['program']); name=st.get('sound_label'); rx=bool(name and 'rx' in name.lower()); dnc=bool(name and 'dnc' in name.lower())
                conflict=status.startswith('IDENTITY_CONFLICT')
                ident=SoundIdentity(st['msb'],st['lsb'],st['program'],name,fam,rx,dnc,conflict)
                out[(ti,idx)]=TrackContext(ti,msg.channel,role,ident,current_element,current_cv,fam,current_track_name)
                out[(ti,idx)].resolution_status=status
    return out


def _classify_detailed_intents(notes, event_contexts, ppq):
    by_tc=defaultdict(list)
    for n in notes: by_tc[(n.track_index,n.channel)].append(n)
    for key,arr in by_tc.items():
        arr.sort(key=lambda n:(n.onset,n.note,n.on_index))
        onset_groups=defaultdict(list)
        for n in arr: onset_groups[n.onset].append(n)
        for i,n in enumerate(arr):
            ctx=event_contexts.get((n.track_index,n.on_index))
            role=ctx.role if ctx else 'UNKNOWN'; fam=ctx.family if ctx else 'UNKNOWN'
            beatpos=(n.onset % (ppq*4))/float(ppq)
            strong=abs(beatpos-round(beatpos))<1e-6 and int(round(beatpos)) in (0,2)
            prev=arr[i-1] if i else None; nxt=arr[i+1] if i+1<len(arr) else None
            if role in ('DRUM','PERC'):
                if len(onset_groups[n.onset])>=3: n.intent='ENSEMBLE_HIT'
                elif strong: n.intent='METRIC_MAIN'
                else: n.intent='SECONDARY_HIT'
            elif role=='BASS' or fam=='BASS':
                if prev and prev.note==n.note: n.intent='REPEATED'
                elif prev and nxt and abs(n.note-prev.note)<=2 and abs(nxt.note-n.note)<=2: n.intent='PASSING_CANDIDATE'
                elif strong: n.intent='METRIC_ANCHOR'
                elif nxt and abs(nxt.note-n.note)<=2: n.intent='APPROACH_CANDIDATE'
                else: n.intent='NORMAL_BASS'
            elif fam=='GUITAR':
                if len(onset_groups[n.onset])>=3: n.intent='CHORD_STRUM'
                elif prev and prev.note==n.note: n.intent='REPEATED_RIFF'
                else: n.intent='GUITAR_LINE'
            elif fam in ('PIANO','ORGAN','ENSEMBLE','SYNTH_PAD','STRINGS','ACCORDION_REED'):
                n.intent='CHORDAL' if len(onset_groups[n.onset])>=2 else ('PHRASE_ACCENT' if strong else 'LINE')
            else:
                n.intent='PHRASE_ACCENT' if strong else 'NORMAL'
    return notes


def _meter_events(mid) -> List[Tuple[int, int, int]]:
    ev = [(0, 4, 4)]
    for tr in mid.tracks:
        for at, _idx, msg in absolute_track(tr):
            if msg.type == 'time_signature':
                ev.append((at, int(msg.numerator), int(msg.denominator)))
    # When multiple tracks carry the same meta event, dedupe.
    return sorted(set(ev), key=lambda x: x[0])


def _metric_position(onset: int, ppq: int, meters: List[Tuple[int, int, int]]) -> Dict[str, Any]:
    cur = meters[0]
    for e in meters:
        if e[0] <= onset:
            cur = e
        else:
            break
    start, num, den = cur
    beat_ticks = ppq * 4.0 / den
    bar_ticks = beat_ticks * num
    rel = max(0.0, onset - start)
    bar_in_segment = int(rel // bar_ticks) + 1 if bar_ticks else 1
    pos = rel % bar_ticks if bar_ticks else 0.0
    beat0 = int(pos // beat_ticks) if beat_ticks else 0
    beat_fraction = (pos / beat_ticks) if beat_ticks else 0.0
    # nearest 1/16 position, expressed 0..15 for a 4/4 bar and proportionally otherwise
    sixteenth_ticks = ppq / 4.0
    subdivision16 = int(round(pos / sixteenth_ticks)) if sixteenth_ticks else 0
    return {
        'meter': '%d/%d' % (num, den),
        'bar_in_meter_segment': bar_in_segment,
        'beat': beat0 + 1,
        'beat_fraction': round(beat_fraction, 4),
        'position_in_bar_ticks': int(round(pos)),
        'subdivision_16_index': subdivision16,
    }


def _local_context(arr: List[Any], i: int, ppq: int, onset_groups: Dict[int, List[Any]]) -> Dict[str, Any]:
    n = arr[i]
    lo = n.onset - ppq * 2
    hi = n.onset + ppq * 2
    local = [x.velocity for x in arr if lo <= x.onset <= hi]
    if not local:
        local = [n.velocity]
    local_sorted = sorted(local)
    p90 = quantiles(local, (.9,))[0]
    med = statistics.median(local)
    rank = sum(1 for x in local if x <= n.velocity) / float(len(local)) * 100.0
    prev = arr[i - 1] if i else None
    nxt = arr[i + 1] if i + 1 < len(arr) else None
    return {
        'window_notes': len(local),
        'min': min(local),
        'median': round(float(med), 2),
        'p90': round(float(p90), 2),
        'max': max(local),
        'delta_from_median': round(float(n.velocity - med), 2),
        'percent_rank': round(rank, 2),
        'is_local_max': n.velocity == max(local),
        'same_onset_count': len(onset_groups.get(n.onset, [])),
        'prev_note': prev.note if prev else None,
        'prev_velocity': prev.velocity if prev else None,
        'prev_interval': n.note - prev.note if prev else None,
        'next_note': nxt.note if nxt else None,
        'next_velocity': nxt.velocity if nxt else None,
        'next_interval': nxt.note - n.note if nxt else None,
        'repeated_from_prev': bool(prev and prev.note == n.note),
    }


def _select_note_profile(registry: ProfileRegistry, ctx, parent: Optional[dict], note: int) -> Tuple[Optional[dict], str]:
    if not ctx or ctx.identity.conflict:
        return None, 'NONE'
    if ctx.family == 'DRUM_KIT' or ctx.role in ('DRUM', 'PERC'):
        dp = registry.resolve_drum_key(ctx.identity.msb, ctx.identity.lsb, ctx.identity.program, note)
        if dp:
            return dp, 'EXACT_DRUM_KEY'
    if parent:
        return parent, 'EXACT_SOUND_ELEMENT' if parent.get('_element_override') else 'EXACT_SOUND'
    return None, 'NONE'


def _note_summary_key(d: dict) -> Tuple[Any, ...]:
    return (d['sound']['address'], d['sound']['name'], d['context']['role'], d['note']['number'])


def _exact_hist_percentile(hist, velocity):
    if not hist:
        return None
    total=sum(hist)
    if total<=0:return None
    v=max(1,min(127,int(velocity)))
    below=sum(hist[:v-1])
    equal=hist[v-1] if v-1<len(hist) else 0
    # midpoint percentile for ties
    return round((below + equal*0.5) / total * 100.0, 3)


def _semantic_detail(semantic_profile, velocity, note, metric):
    if not semantic_profile:
        return {'available':False}
    hist=semantic_profile.get('histogram_1_127') or []
    modes=semantic_profile.get('modes') or []
    valleys=semantic_profile.get('valleys') or []
    nearest=None
    if modes:
        nearest=min(modes,key=lambda m:abs(int(m.get('center',64))-velocity))
    # A valley is potentially a semantic boundary. We do not name the meaning;
    # we only report proximity/crossing risk.
    near_valleys=[v for v in valleys if abs(int(v.get('velocity',-999))-velocity)<=2]
    pprof=(semantic_profile.get('pitch_velocity') or {}).get(str(note))
    bkey=f"{metric.get('meter')}:{metric.get('subdivision_16_index')}"
    bprof=(semantic_profile.get('beat_velocity') or {}).get(bkey)
    def compact_cond(p):
        if not p:return None
        return {'n':p.get('n'),'summary':p.get('summary'),'modes':p.get('modes',[]),'valleys':p.get('valleys',[])}
    def compact_delta(p):
        if not p:return None
        return {k:v for k,v in p.items() if not k.startswith('histogram_')}
    return {
      'available':True,
      'support':semantic_profile.get('support',{}),
      'exact_histogram_percentile':_exact_hist_percentile(hist,velocity),
      'modes':modes,
      'nearest_mode':nearest,
      'valleys':valleys,
      'near_semantic_valley':near_valleys,
      'pitch_specific':compact_cond(pprof),
      'beat_specific_key':bkey,
      'beat_specific':compact_cond(bprof),
      'sequence_delta':compact_delta(semantic_profile.get('sequence_delta')),
      'repeated_pitch_delta':compact_delta(semantic_profile.get('repeated_pitch_delta')),
    }


def _semantic_ceiling(semantic_detail, intent, fallback):
    """Analysis-only multi-axis ceiling. Never used as a mutation permission."""
    candidates=[]
    # context profile envelope
    if fallback is not None:candidates.append(('profile',fallback))
    for label in ('pitch_specific','beat_specific'):
        p=semantic_detail.get(label) if semantic_detail else None
        if p and int(p.get('n',0))>=100:
            s=p.get('summary') or {}
            if intent in SOFT_INTENTS:
                val=_iround(s.get('ideal_max'))
            elif intent in ACCENT_INTENTS:
                val=_iround(s.get('p95')) or _iround(s.get('working_max'))
            else:
                val=_iround(s.get('working_max'))
            if val is not None:candidates.append((label,val))
    if not candidates:return None,[]
    # Median resists one unusually low/high conditional bucket.
    vals=sorted(v for _,v in candidates)
    med=int(round(statistics.median(vals)))
    return max(1,min(127,med)),[{'source':k,'max':v} for k,v in candidates]


def _previous_distinct_onset(arr,i):
    onset=arr[i].onset
    j=i-1
    while j>=0:
        if arr[j].onset<onset:return arr[j]
        j-=1
    return None

@dataclass
class DetectorOptions:
    protect_rx_low_velocity: bool = True
    protect_rx_special_pitch: bool = True


class NoteVelocityMaxDetector:
    """Read-only detector producing a detailed per-note velocity/MAX report."""

    schema_version = 2

    def __init__(self, registry: Optional[ProfileRegistry] = None, options: Optional[DetectorOptions] = None):
        self.registry = registry or ProfileRegistry()
        self.options = options or DetectorOptions()

    def analyze(self, input_path: str) -> Dict[str, Any]:
        mid = load_midi(input_path)
        # Track-level contexts remain useful for summary/fallback, but detection is
        # resolved at each Note-On event so concatenated Style Elements and
        # per-section Sound changes are represented correctly.
        contexts = build_contexts(mid, self.registry)
        event_contexts = _build_note_event_contexts(mid, self.registry)
        notes = extract_notes(mid)
        _classify_detailed_intents(notes, event_contexts, mid.ticks_per_beat)
        meters = _meter_events(mid)
        controller_states = build_controller_states(mid)
        tempos = tempo_events(mid)

        cfg = OptimizeConfig(
            protect_rx_low_velocity=self.options.protect_rx_low_velocity,
            protect_rx_special_pitch=self.options.protect_rx_special_pitch,
            enable_velocity=False,
            enable_timing=False,
            enable_gate=False,
        )

        by_tc = defaultdict(list)
        for n in notes:
            by_tc[(n.track_index, n.channel)].append(n)
        for arr in by_tc.values():
            arr.sort(key=lambda n: (n.onset, n.note, n.on_index))

        detections: List[Dict[str, Any]] = []
        for key, arr in by_tc.items():
            onset_groups = defaultdict(list)
            for n in arr:
                onset_groups[n.onset].append(n)

            for i, n in enumerate(arr):
                ctx = event_contexts.get((n.track_index,n.on_index)) or contexts.get(key)
                p,status = self.registry.resolve_identity_with_name(
                    ctx.identity.msb if ctx else None,
                    ctx.identity.lsb if ctx else None,
                    ctx.identity.program if ctx else None,
                    ctx.identity.name if ctx else None,
                    ctx.role if ctx else None,
                )
                parent = self.registry.choose_element_profile(p,ctx.element) if p and ctx else p
                profile, source = _select_note_profile(self.registry, ctx, parent, n.note)
                lim = _velocity_limits(profile)
                manual_dnc=self.registry.resolve_manual_dnc(
                    ctx.identity.msb if ctx else None, ctx.identity.lsb if ctx else None, ctx.identity.program if ctx else None
                )
                # RX special-pitch protection is a Sound-level property; Drum-key
                # profile remains the velocity source but the parent profile is
                # used for safety semantics. DNC exact identities come from manual.
                protected, protect_reason = protect_note(n, ctx, parent or profile, cfg, manual_dnc=manual_dnc)
                contextual_max, max_policy = _contextual_max(n.intent, lim, protected, n.velocity)
                z = _zone(n.velocity, lim)
                local = _local_context(arr, i, mid.ticks_per_beat, onset_groups)
                metric = _metric_position(n.onset, mid.ticks_per_beat, meters)
                semprof, semsource = self.registry.resolve_velocity_semantics(
                    ctx.identity.msb if ctx else None, ctx.identity.lsb if ctx else None, ctx.identity.program if ctx else None,
                    ctx.identity.name if ctx else None, ctx.role if ctx else None, ctx.element if ctx else None, ctx.cv if ctx else None
                )
                semdetail=_semantic_detail(semprof,n.velocity,n.note,metric)
                semantic_max, semantic_max_sources=_semantic_ceiling(semdetail,n.intent,contextual_max)
                prev_distinct=_previous_distinct_onset(arr,i)
                arranger_atom=self.registry.arranger_element_role(ctx.element,ctx.role) if ctx else None
                dnc_state=evaluate_dnc_note(
                    n,ctx,manual_dnc,controller_states.get((n.track_index,n.on_index),{}),prev_distinct,mid.ticks_per_beat,tempos
                )
                support = _profile_support(profile)
                sp = bool(ctx and special_pitch(parent or profile, n.note))
                rawmax = lim.get('raw_max')
                workingmax = lim.get('working_max')
                idealmax = lim.get('ideal_max')

                d = {
                    'track': n.track_index,
                    'channel': n.channel + 1,
                    'track_name': ctx.track_name if ctx else '',
                    'sound': {
                        'address': '%s.%s.%s' % (
                            ctx.identity.msb if ctx else None,
                            ctx.identity.lsb if ctx else None,
                            ctx.identity.program if ctx else None,
                        ),
                        'msb': ctx.identity.msb if ctx else None,
                        'lsb': ctx.identity.lsb if ctx else None,
                        'program': ctx.identity.program if ctx else None,
                        'name': ctx.identity.name if ctx else None,
                        'family': ctx.family if ctx else 'UNKNOWN',
                        'rx_named': bool(ctx and ctx.identity.rx_named),
                        'dnc_named': bool(ctx and ctx.identity.dnc_named),
                        'identity_conflict': bool(ctx and ctx.identity.conflict),
                        'resolution': getattr(ctx,'resolution_status',status if ctx else 'NO_CONTEXT'),
                    },
                    'context': {
                        'role': ctx.role if ctx else 'UNKNOWN',
                        'element': ctx.element if ctx else None,
                        'cv': ctx.cv if ctx else None,
                        'intent': n.intent,
                        **metric,
                    },
                    'note': {
                        'number': n.note,
                        'name': midi_note_name(n.note),
                        'onset_tick': n.onset,
                        'off_tick': n.off,
                        'duration_ticks': n.duration,
                        'velocity': n.velocity,
                    },
                    'profile': {
                        'source': source,
                        'support': support,
                        'velocity_limits': lim,
                        'velocity_modes': (profile or {}).get('velocity_modes', []),
                        'semantic_source': semsource,
                        'semantic': semdetail,
                    },
                    'velocity_detection': {
                        'zone': z,
                        'estimated_factory_percentile': _estimated_percentile(n.velocity, lim),
                        'ideal_max': idealmax,
                        'working_max': workingmax,
                        'contextual_max': contextual_max,
                        'contextual_max_policy': max_policy,
                        'semantic_contextual_max': semantic_max,
                        'semantic_contextual_max_sources': semantic_max_sources,
                        'factory_raw_max': rawmax,
                        'midi_absolute_max': 127,
                        'headroom_to_ideal_max': (idealmax - n.velocity) if idealmax is not None else None,
                        'headroom_to_working_max': (workingmax - n.velocity) if workingmax is not None else None,
                        'headroom_to_contextual_max': (contextual_max - n.velocity) if contextual_max is not None else None,
                        'headroom_to_semantic_contextual_max': (semantic_max - n.velocity) if semantic_max is not None else None,
                        'headroom_to_factory_raw_max': (rawmax - n.velocity) if rawmax is not None else None,
                        'headroom_to_midi_127': 127 - n.velocity,
                        'at_midi_max_127': n.velocity == 127,
                        'at_or_above_working_max': bool(workingmax is not None and n.velocity >= workingmax),
                        'above_contextual_max': bool(contextual_max is not None and n.velocity > contextual_max),
                        'above_factory_raw_max': bool(rawmax is not None and n.velocity > rawmax),
                        'action': _action(n.velocity, contextual_max, lim, protected),
                    },
                    'special_safety': {
                        'protected': protected,
                        'reason': protect_reason,
                        'special_pitch_candidate': sp,
                    },
                    'dnc_manual_state': dnc_state,
                    'arranger_factory_context': arranger_atom,
                    'local_context': local,
                }
                detections.append(d)

        return self._finalize(input_path, mid, detections, contexts)

    def _finalize(self, input_path, mid, detections, contexts):
        zones = Counter(d['velocity_detection']['zone'] for d in detections)
        actions = Counter(d['velocity_detection']['action'] for d in detections)
        sources = Counter(d['profile']['source'] for d in detections)
        protected = sum(1 for d in detections if d['special_safety']['protected'])
        over_context = [d for d in detections if d['velocity_detection']['above_contextual_max']]
        at127 = [d for d in detections if d['velocity_detection']['at_midi_max_127']]

        # Note-number summaries per exact sound/role.
        grouped = defaultdict(list)
        for d in detections:
            grouped[_note_summary_key(d)].append(d)
        note_summaries = []
        for (addr, sound, role, note), arr in grouped.items():
            vals = [x['note']['velocity'] for x in arr]
            q10, q25, q50, q75, q90 = quantiles(vals)
            cmaxes = [x['velocity_detection']['contextual_max'] for x in arr if x['velocity_detection']['contextual_max'] is not None]
            wmaxes = [x['velocity_detection']['working_max'] for x in arr if x['velocity_detection']['working_max'] is not None]
            note_summaries.append({
                'address': addr,
                'sound': sound,
                'role': role,
                'note': note,
                'note_name': midi_note_name(note),
                'count': len(arr),
                'velocity_min': min(vals),
                'velocity_p10': round(q10, 2),
                'velocity_p25': round(q25, 2),
                'velocity_median': round(q50, 2),
                'velocity_p75': round(q75, 2),
                'velocity_p90': round(q90, 2),
                'velocity_max_in_input': max(vals),
                'profile_working_max': int(round(statistics.median(wmaxes))) if wmaxes else None,
                'contextual_max_median': int(round(statistics.median(cmaxes))) if cmaxes else None,
                'midi_127_count': sum(1 for x in vals if x == 127),
                'over_contextual_max_count': sum(1 for x in arr if x['velocity_detection']['above_contextual_max']),
                'protected_count': sum(1 for x in arr if x['special_safety']['protected']),
            })
        note_summaries.sort(key=lambda x: (x['over_contextual_max_count'], x['count'], x['velocity_max_in_input']), reverse=True)

        # Mark each occurrence against the maximum actually present for the same
        # exact Sound/role/note number in this input.
        group_input_max={k:max(x['note']['velocity'] for x in arr) for k,arr in grouped.items()}
        for d in detections:
            mx=group_input_max[_note_summary_key(d)]
            d['velocity_detection']['input_same_note_max']=mx
            d['velocity_detection']['is_input_same_note_max']=d['note']['velocity']==mx

        track_summaries = []
        by_track = defaultdict(list)
        for d in detections:
            by_track[(d['track'], d['channel'])].append(d)
        for (ti, ch), arr in sorted(by_track.items()):
            vals = [x['note']['velocity'] for x in arr]
            track_max=max(vals)
            for x in arr:
                x['velocity_detection']['input_track_max']=track_max
                x['velocity_detection']['is_input_track_max']=x['note']['velocity']==track_max
            first = arr[0]
            track_summaries.append({
                'track': ti,
                'channel': ch,
                'track_name': first['track_name'],
                'address': first['sound']['address'],
                'sound': first['sound']['name'],
                'family': first['sound']['family'],
                'role': first['context']['role'],
                'element': first['context']['element'],
                'cv': first['context']['cv'],
                'notes': len(arr),
                'velocity_min': min(vals),
                'velocity_median': round(float(statistics.median(vals)), 2),
                'velocity_max': max(vals),
                'at_127': sum(1 for x in vals if x == 127),
                'over_contextual_max': sum(1 for x in arr if x['velocity_detection']['above_contextual_max']),
                'protected': sum(1 for x in arr if x['special_safety']['protected']),
                'profile_sources': dict(Counter(x['profile']['source'] for x in arr)),
            })

        # Highest-priority review list: most excessive first.
        def excess(d):
            h = d['velocity_detection']['headroom_to_contextual_max']
            return -(h if h is not None else 0)
        review = sorted(
            [d for d in detections if d['velocity_detection']['action'] not in ('WITHIN_PROFILE',)],
            key=lambda d: (d['velocity_detection']['above_contextual_max'], excess(d), d['note']['velocity']),
            reverse=True,
        )[:500]

        return {
            'schema': 'PA800_NOTE_VELOCITY_MAX_DETECTION',
            'schema_version': self.schema_version,
            'input_file': str(input_path),
            'midi': {
                'type': mid.type,
                'ticks_per_beat': mid.ticks_per_beat,
                'tracks': len(mid.tracks),
                'detected_notes': len(detections),
            },
            'summary': {
                'notes': len(detections),
                'with_profile': sum(1 for d in detections if d['profile']['source'] != 'NONE'),
                'without_profile': sum(1 for d in detections if d['profile']['source'] == 'NONE'),
                'protected': protected,
                'velocity_127': len(at127),
                'over_contextual_max': len(over_context),
                'zones': dict(zones),
                'actions': dict(actions),
                'profile_sources': dict(sources),
            },
            'track_summaries': track_summaries,
            'note_number_summaries': note_summaries,
            'priority_review': review,
            'detections': detections,
        }

    @staticmethod
    def write_json(report: Dict[str, Any], output_path: str) -> None:
        Path(output_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    @staticmethod
    def write_csv(report: Dict[str, Any], output_path: str) -> None:
        fields = [
            'track', 'channel', 'track_name', 'address', 'sound', 'family', 'role', 'element', 'cv',
            'intent', 'bar', 'beat', 'note', 'note_name', 'velocity', 'duration_ticks',
            'profile_source', 'support_grade', 'support_count', 'factory_percentile', 'zone',
            'ideal_max', 'working_max', 'contextual_max', 'contextual_max_policy', 'factory_raw_max',
            'headroom_contextual', 'at_127', 'above_contextual_max', 'action',
            'protected', 'protect_reason', 'special_pitch_candidate',
            'semantic_profile_source','semantic_hist_percentile','semantic_contextual_max','nearest_velocity_mode','near_semantic_valley',
            'pitch_specific_working_max','beat_specific_working_max','dnc_manual_name','dnc_active_candidates',
            'cc80_sc1','cc81_sc2','cc1_yplus','cc2_yminus','cc64_damper','aftertouch',
            'local_median', 'local_max', 'local_percent_rank', 'same_onset_count'
        ]
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for d in report['detections']:
                vd = d['velocity_detection']; lc = d['local_context']; sp = d['special_safety']; sup = d['profile']['support']
                sem=d['profile'].get('semantic') or {}; dnc=d.get('dnc_manual_state') or {}; cs=dnc.get('controller_state') or {}
                psp=sem.get('pitch_specific') or {}; bsp=sem.get('beat_specific') or {}
                w.writerow({
                    'track': d['track'], 'channel': d['channel'], 'track_name': d['track_name'],
                    'address': d['sound']['address'], 'sound': d['sound']['name'], 'family': d['sound']['family'],
                    'role': d['context']['role'], 'element': d['context']['element'], 'cv': d['context']['cv'],
                    'intent': d['context']['intent'], 'bar': d['context']['bar_in_meter_segment'], 'beat': d['context']['beat'],
                    'note': d['note']['number'], 'note_name': d['note']['name'], 'velocity': d['note']['velocity'],
                    'duration_ticks': d['note']['duration_ticks'], 'profile_source': d['profile']['source'],
                    'support_grade': sup['grade'], 'support_count': sup['notes_or_hits'],
                    'factory_percentile': vd['estimated_factory_percentile'], 'zone': vd['zone'],
                    'ideal_max': vd['ideal_max'], 'working_max': vd['working_max'],
                    'contextual_max': vd['contextual_max'], 'contextual_max_policy': vd['contextual_max_policy'],
                    'factory_raw_max': vd['factory_raw_max'], 'headroom_contextual': vd['headroom_to_contextual_max'],
                    'at_127': vd['at_midi_max_127'], 'above_contextual_max': vd['above_contextual_max'],
                    'action': vd['action'], 'protected': sp['protected'], 'protect_reason': sp['reason'],
                    'special_pitch_candidate': sp['special_pitch_candidate'],
                    'semantic_profile_source': d['profile'].get('semantic_source'),
                    'semantic_hist_percentile': sem.get('exact_histogram_percentile'),
                    'semantic_contextual_max': vd.get('semantic_contextual_max'),
                    'nearest_velocity_mode': (sem.get('nearest_mode') or {}).get('center'),
                    'near_semantic_valley': ','.join(str(x.get('velocity')) for x in sem.get('near_semantic_valley',[])),
                    'pitch_specific_working_max': (psp.get('summary') or {}).get('working_max'),
                    'beat_specific_working_max': (bsp.get('summary') or {}).get('working_max'),
                    'dnc_manual_name': dnc.get('manual_name'),
                    'dnc_active_candidates': ','.join(dnc.get('active_candidates',[])),
                    'cc80_sc1': cs.get('cc80'), 'cc81_sc2': cs.get('cc81'), 'cc1_yplus': cs.get('cc1'), 'cc2_yminus': cs.get('cc2'),
                    'cc64_damper': cs.get('cc64'), 'aftertouch': cs.get('aftertouch'),
                    'local_median': lc['median'],
                    'local_max': lc['max'], 'local_percent_rank': lc['percent_rank'], 'same_onset_count': lc['same_onset_count'],
                })