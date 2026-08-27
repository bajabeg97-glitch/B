"""Factory/Gold evidence router for musical pattern review candidates.

This module never edits MIDI. It exposes what the neural/pattern layer may
analyze and rank while deterministic, verified engines retain write authority.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import Counter, defaultdict
import json
from pathlib import Path
import re

from .corpus_router import route_authority

SCHEMA = 'PA800_PATTERN_ADVISOR_V2'
GENERATOR_SCHEMA = 'PA800_CHORD_PATTERN_GENERATOR_V1'
LEAD_FAMILIES = {'REED', 'PIPE', 'ACCORDION', 'ACCORDION_REED', 'HARMONICA', 'SYNTH_LEAD', 'ETHNIC'}
TONAL_FAMILIES = {'BASS','GUITAR','PIANO','ACCORDION','HARMONICA','STRINGS','ENSEMBLE','CHOIR_VOICE','BRASS','REED','PIPE','ORGAN','SYNTH_PAD','SYNTH_LEAD','CHROMATIC_PERC','MALLET','PLUCK','ETHNIC'}
ROOTS={'C':0,'C#':1,'DB':1,'D':2,'D#':3,'EB':3,'E':4,'F':5,'F#':6,'GB':6,'G':7,'G#':8,'AB':8,'A':9,'A#':10,'BB':10,'B':11}
QUALITY_ALIASES={'':'MAJOR','M':'MINOR','MIN':'MINOR','MINOR':'MINOR','MAJ':'MAJOR','MAJOR':'MAJOR','7':'DOM7','DOM7':'DOM7','MAJ7':'MAJ7','M7':'MIN7','MIN7':'MIN7','DIM':'DIM','DIM7':'DIM7','AUG':'AUG','+':'AUG','SUS':'SUS4','SUS4':'SUS4','SUS2':'SUS2','5':'POWER5'}
CHORD_INTERVALS={'MAJOR':(0,4,7),'MINOR':(0,3,7),'DOM7':(0,4,7,10),'MAJ7':(0,4,7,11),'MIN7':(0,3,7,10),'DIM':(0,3,6),'DIM7':(0,3,6,9),'AUG':(0,4,8),'SUS2':(0,2,7),'SUS4':(0,5,7),'POWER5':(0,7)}
SCALE_INTERVALS={'MAJOR':(0,2,4,5,7,9,11),'DOM7':(0,2,4,5,7,9,10),'MAJ7':(0,2,4,5,7,9,11),'MINOR':(0,2,3,5,7,8,10),'MIN7':(0,2,3,5,7,8,10),'DIM':(0,2,3,5,6,8,9,11),'DIM7':(0,2,3,5,6,8,9,11),'AUG':(0,2,4,6,8,10),'SUS2':(0,2,4,5,7,9,11),'SUS4':(0,2,4,5,7,9,11),'POWER5':(0,2,4,5,7,9,10)}
FAMILY_RANGES={'BASS':(28,64),'GUITAR':(40,92),'PIANO':(24,108),'ACCORDION':(41,100),'HARMONICA':(48,100),'STRINGS':(36,108),'ENSEMBLE':(36,108),'CHOIR_VOICE':(40,100),'BRASS':(40,94),'REED':(46,104),'PIPE':(48,108),'ORGAN':(24,108),'SYNTH_PAD':(32,108),'SYNTH_LEAD':(48,112),'CHROMATIC_PERC':(36,100),'MALLET':(36,100),'PLUCK':(36,100),'ETHNIC':(40,108)}


def _heads(family, role, content_type):
    family = str(family or 'UNKNOWN').upper()
    role = str(role or '').upper()
    heads = []
    if family in {'DRUM_KIT', 'PERCUSSIVE'}:
        heads.append('DRUM_PATTERN')
        if content_type == 'style' or 'FILL' in role or 'BREAK' in role:
            heads.extend(('FILL_STRUCTURE', 'FILL_CONTENT'))
    if family == 'BASS': heads.append('BASS_PATTERN')
    if family == 'GUITAR':
        heads.extend(('GUITAR_MODE', 'GUITAR_STRUM'))
        if any(word in role for word in ('POWER', 'DIST', 'GTR', 'ACC')):
            heads.extend(('POWERCHORD_VOICING', 'POWERCHORD_RIFF'))
    if family == 'BRASS': heads.append('BRASS_PATTERN')
    if family in {'STRINGS', 'ENSEMBLE', 'SYNTH_PAD'}: heads.append('STRINGS_PAD_PATTERN')
    if family in LEAD_FAMILIES or any(word in role for word in ('LEAD', 'SOLO', 'COUNTER')):
        heads.extend(('SOLO_PHRASE', 'EXPRESSION_CC11', 'ORNAMENT'))
    return tuple(dict.fromkeys(heads))


def analyze_pattern_advisor(notes, contexts, content_type='auto'):
    by_context = defaultdict(list)
    for note in notes:
        by_context[(int(note.track_index), int(note.channel))].append(note)
    candidates = []
    for key, ctx in sorted(contexts.items()):
        identity = getattr(ctx, 'identity', None)
        family = getattr(ctx, 'family', None) or getattr(identity, 'org_family', None) or getattr(identity, 'family', None) or 'UNKNOWN'
        role = getattr(ctx, 'role', None) or getattr(identity, 'role', None) or ''
        rows = by_context.get((int(key[0]), int(key[1])), [])
        if not rows: continue
        onsets = {int(note.onset) for note in rows}
        pitches = {int(note.note) for note in rows}
        for head in _heads(family, role, str(content_type).lower()):
            route = route_authority(head)
            candidates.append({
                'track': int(key[0]), 'channel': int(key[1]) + 1,
                'family': str(family).upper(), 'role': str(role), 'head': head,
                'route': route, 'evidence': {'notes': len(rows), 'unique_onsets': len(onsets),
                    'pitch_span': max(pitches)-min(pitches) if pitches else 0},
                'action': 'ANALYZE_AND_RANK', 'applied': False,
                'velocity_policy': 'PROFILE_ONLY',
                'guards': ['FACTORY_STRUCTURE_AND_PA800_SAFETY', 'GOLD_PERFORMANCE_EVIDENCE',
                    'PROPOSAL_POLICY_SIMULATOR_TRANSACTION_VALIDATION_EXPORT'],
            })
    counts = Counter(row['head'] for row in candidates)
    return {'schema': SCHEMA, 'analyzer_only': True, 'authority_granted': False,
            'mutations': 0, 'applied_actions': 0,
            'velocity_neural_input': False, 'velocity_neural_output': False,
            'chord_generator': {'available': True, 'mode': 'EXPLICIT_RETRIEVAL_REVOICE',
                'allowed_mutation': 'PITCH_ONLY_ON_UNPROTECTED_TONAL_NOTES',
                'preserved': ['RHYTHM','VELOCITY','GATE','SOUND','RX_DNC','CONTROLLERS','META','TRACK_LENGTH']},
            'candidates': candidates,
            'summary': {'contexts': len({(row['track'], row['channel']) for row in candidates}),
                        'candidates': len(candidates), 'heads': dict(sorted(counts.items()))},
            'policy': 'Factory constrains PA800 structure/safety; Gold supplies Balkan performance evidence; review required'}


def validate_pattern_advisor(report):
    candidates = report.get('candidates') or []
    errors = []
    if report.get('schema') != SCHEMA: errors.append('schema')
    if report.get('analyzer_only') is not True or report.get('authority_granted') is not False: errors.append('authority')
    if report.get('mutations') != 0 or report.get('applied_actions') != 0 or any(row.get('applied') for row in candidates): errors.append('mutation')
    if report.get('velocity_neural_input') is not False or report.get('velocity_neural_output') is not False: errors.append('velocity_boundary')
    if any(row.get('head') == 'VELOCITY' or row.get('velocity_policy') != 'PROFILE_ONLY' for row in candidates): errors.append('velocity_route')
    return {'pass': not errors, 'errors': errors, 'candidates': len(candidates)}


def parse_chord_progression(text):
    """Parse C, Cm, C7, Cmaj7, C/E and optional repetition (Am*2)."""
    raw=str(text or '').strip()
    if not raw:raise ValueError('Upiši akorde, npr. C | Am | F | G7')
    tokens=[token for token in re.split(r'[|,;\s]+',raw) if token]
    result=[]
    pattern=re.compile(r'^([A-Ga-g])([#b]?)(maj7|min7|m7|maj|min|dim7|dim|aug|sus2|sus4|sus|m|7|5|\+)?(?:/([A-Ga-g])([#b]?))?(?:\*(\d+))?$')
    for token in tokens:
        match=pattern.match(token)
        if not match:raise ValueError('Nepoznat akord: %s' % token)
        root=(match.group(1)+match.group(2)).upper();root_display=match.group(1).upper()+match.group(2).replace('B','b');quality_text=match.group(3) or '';quality=QUALITY_ALIASES.get(quality_text.upper())
        if root not in ROOTS or quality not in CHORD_INTERVALS:raise ValueError('Nepodržan akord: %s' % token)
        bass=((match.group(4) or '')+(match.group(5) or '')).upper() or root;bass_display=(match.group(4).upper()+match.group(5).replace('B','b')) if match.group(4) else root_display
        if bass not in ROOTS:raise ValueError('Nepodržan slash bass: %s' % token)
        repeat=max(1,min(64,int(match.group(6) or 1)))
        canonical=root_display+({'MAJOR':'','MINOR':'m','DOM7':'7','MAJ7':'maj7','MIN7':'m7','DIM':'dim','DIM7':'dim7','AUG':'aug','SUS2':'sus2','SUS4':'sus4','POWER5':'5'}[quality])+('/'+bass_display if bass!=root else '')
        row={'label':canonical,'root':ROOTS[root],'root_name':root_display,'quality':quality,'bass':ROOTS[bass],'bass_name':bass_display,'chord_intervals':list(CHORD_INTERVALS[quality]),'scale_intervals':list(SCALE_INTERVALS[quality])}
        result.extend(dict(row) for _ in range(repeat))
    if len(result)>1024:raise ValueError('Previše taktova u progresiji (maksimalno 1024).')
    return result


def _infer_source_chord(notes):
    counts=Counter(int(note.note)%12 for note in notes)
    if not counts:return {'label':'C','root':0,'quality':'MAJOR','chord_intervals':[0,4,7],'scale_intervals':[0,2,4,5,7,9,11]}
    candidates=[]
    for root in range(12):
        for quality in ('MAJOR','MINOR','DOM7'):
            chord={(root+interval)%12 for interval in CHORD_INTERVALS[quality]};score=sum(counts[pitch]*(2.0 if pitch==root else 1.0) for pitch in chord)-sum(counts[pitch]*.18 for pitch in counts if pitch not in chord)
            candidates.append((score,root,quality))
    _score,root,quality=max(candidates,key=lambda row:(row[0],-row[1],row[2]=='MAJOR'))
    return {'label':'INFERRED_%d_%s'%(root,quality),'root':root,'quality':quality,'chord_intervals':list(CHORD_INTERVALS[quality]),'scale_intervals':list(SCALE_INTERVALS[quality])}


def _style_source_chord(ctx):
    cv=int(getattr(ctx,'cv',0) or 0);quality='MINOR' if cv==2 else 'DOM7' if cv==3 else 'MAJOR'
    return {'label':'C'+('m' if quality=='MINOR' else '7' if quality=='DOM7' else ''),'root':0,'quality':quality,'chord_intervals':list(CHORD_INTERVALS[quality]),'scale_intervals':list(SCALE_INTERVALS[quality])}


def _nearest_pc(reference,pitch_class,low,high):
    values=[pitch for pitch in range(max(0,int(low)),min(127,int(high))+1) if pitch%12==pitch_class%12]
    return min(values,key=lambda pitch:(abs(pitch-reference),pitch)) if values else int(max(0,min(127,reference)))


def _degree_map(pitch,source,target,family,role):
    src_root=int(source['root']);target_root=int(target['root']);relative=(int(pitch)-src_root)%12
    src_chord=list(source['chord_intervals']);target_chord=list(target['chord_intervals']);src_scale=list(source['scale_intervals']);target_scale=list(target['scale_intervals'])
    power=family=='GUITAR' and any(word in str(role or '').upper() for word in ('POWER','RIFF','DIST'))
    if power:
        degree=0 if min((relative-0)%12,(0-relative)%12)<=min((relative-7)%12,(7-relative)%12) else 1
        target_interval=(0,7)[degree]
    elif relative in src_chord:
        degree=src_chord.index(relative)
        if family=='BASS' and degree==0 and int(target.get('bass',target_root))!=target_root:target_interval=(int(target['bass'])-target_root)%12
        elif degree<len(target_chord):target_interval=target_chord[degree]
        elif degree==3:target_interval=target_scale[-1]
        else:target_interval=target_chord[-1]
    else:
        degree=min(range(len(src_scale)),key=lambda index:min((relative-src_scale[index])%12,(src_scale[index]-relative)%12));target_interval=target_scale[min(degree,len(target_scale)-1)]
    wanted_pc=(target_root+target_interval)%12;root_shift=((target_root-src_root+6)%12)-6;reference=int(pitch)+root_shift
    low,high=FAMILY_RANGES.get(family,(0,127));return _nearest_pc(reference,wanted_pc,low,high)


def _collision_safe_pitch(proposal,note,target,family,occupied,role=''):
    keybase=(int(note.track_index),int(note.channel));low,high=FAMILY_RANGES.get(family,(0,127))
    candidates=[proposal]
    for delta in (12,-12,24,-24):
        value=proposal+delta
        if low<=value<=high:candidates.append(value)
    intervals=(0,7) if family=='GUITAR' and any(word in str(role).upper() for word in ('POWER','RIFF','DIST')) else target['chord_intervals']
    for interval in intervals:
        candidates.append(_nearest_pc(proposal,(target['root']+interval)%12,low,high))
    for value in dict.fromkeys(candidates):
        collisions=[row for row in occupied.get((*keybase,value),[]) if max(int(note.onset),row[0])<min(int(note.off),row[1]) and row[2]!=int(note.note)]
        if not collisions:return value,False
    return int(note.note),True


def _generator_scan(mid):
    tracks=[]
    for track in mid.tracks:
        tick=0;events=[]
        for ordinal,msg in enumerate(track):
            tick+=int(msg.time);data=msg.dict();data.pop('time',None)
            events.append({'ordinal':ordinal,'tick':tick,'type':msg.type,'data':data})
        tracks.append({'end_tick':tick,'events':events})
    return {'type':mid.type,'ticks_per_beat':mid.ticks_per_beat,'tracks':tracks}


def validate_generated_pattern(before,after,changes,chords):
    """Pitch-only verifier for the explicit Pattern Brain generation path."""
    a=_generator_scan(before);b=_generator_scan(after);errors=[]
    if a['type']!=b['type']:errors.append('SMF_TYPE_CHANGED')
    if a['ticks_per_beat']!=b['ticks_per_beat']:errors.append('TPB_CHANGED')
    if len(a['tracks'])!=len(b['tracks']):errors.append('TRACK_COUNT_CHANGED')
    if [row['end_tick'] for row in a['tracks']]!=[row['end_tick'] for row in b['tracks']]:errors.append('TRACK_LENGTH_CHANGED')
    allowed={(int(row['track']),int(row['on_index'])):(int(row['old']),int(row['new'])) for row in changes};allowed.update({(int(row['track']),int(row['off_index'])):(int(row['old']),int(row['new'])) for row in changes})
    actual_changes=[]
    for track_index,(left,right) in enumerate(zip(a['tracks'],b['tracks'])):
        if len(left['events'])!=len(right['events']):errors.append('EVENT_COUNT_CHANGED:%d'%track_index);continue
        for old,new in zip(left['events'],right['events']):
            if (old['ordinal'],old['tick'],old['type'])!=(new['ordinal'],new['tick'],new['type']):errors.append('EVENT_ORDER_OR_TIME_CHANGED:%d:%d'%(track_index,old['ordinal']));continue
            old_data=dict(old['data']);new_data=dict(new['data']);old_note=old_data.pop('note',None);new_note=new_data.pop('note',None)
            if old_data!=new_data:errors.append('NON_PITCH_EVENT_CHANGED:%d:%d'%(track_index,old['ordinal']))
            if old_note!=new_note:
                actual_changes.append((track_index,old['ordinal'],old_note,new_note))
                if allowed.get((track_index,old['ordinal']))!=(old_note,new_note):errors.append('UNAUTHORIZED_PITCH_CHANGE:%d:%d'%(track_index,old['ordinal']))
    expected={(track,index,old,new) for (track,index),(old,new) in allowed.items()};actual=set(actual_changes)
    if actual!=expected:errors.append('PITCH_LEDGER_MISMATCH')
    for row in changes:
        chord=chords[(int(row['bar'])-1)%len(chords)];family=str(row.get('family','UNKNOWN'));role=str(row.get('role','')).upper();power=family=='GUITAR' and any(word in role for word in ('POWER','RIFF','DIST'));intervals=(0,7) if power else tuple(chord['scale_intervals']);allowed_pcs={(int(chord['root'])+interval)%12 for interval in intervals};new=int(row['new']);low,high=FAMILY_RANGES.get(family,(0,127))
        if not 0<=new<=127 or not low<=new<=high:errors.append('FAMILY_RANGE_VIOLATION:%s:%s'%(family,new))
        if new%12 not in allowed_pcs:errors.append('CHORD_SCALE_VIOLATION:%s:%s:%s'%(row['bar'],chord['label'],new))
    return {'schema':'PA800_CHORD_PATTERN_VERIFIER_V1','pass':not errors,'errors':errors,'authorized_note_pairs':len(changes),'authorized_pitch_events':len(allowed),'actual_pitch_events':len(actual),'chord_bars':len(chords),'checks':{'structure_preserved':not any(error.startswith(('SMF_','TPB_','TRACK_','EVENT_COUNT','EVENT_ORDER')) for error in errors),'non_pitch_data_preserved':not any(error.startswith('NON_PITCH') for error in errors),'pitch_authority_exact':not any(error.startswith(('UNAUTHORIZED','PITCH_LEDGER')) for error in errors),'harmonic_conformity':not any(error.startswith(('FAMILY_RANGE','CHORD_SCALE')) for error in errors)}}


def generate_chord_pattern(input_path,output_path,progression,include_solo=True,content_type='auto',registry=None):
    """Create a pitch-revoiced pattern while preserving the template performance.

    Factory/Gold MIDI supplies every rhythm, velocity, gate, controller and
    Sound event. Only unprotected tonal note pitches receive chord authority.
    """
    from ..analysis.context import build_contexts,detect_content_type_details
    from ..analysis.meter_map import _build_bar_spans
    from ..config import OptimizeConfig
    from ..core.midi_io import extract_notes,load_midi,save_midi
    from ..instruments.policies import policy_for
    from ..profiles.registry import ProfileRegistry
    from ..safety.rx_dnc import protect_note
    chords=parse_chord_progression(progression) if isinstance(progression,str) else list(progression)
    source_path=Path(input_path);target_path=Path(output_path)
    if source_path.resolve()==target_path.resolve():raise ValueError('Generator output mora biti druga datoteka od template MIDI-ja.')
    mid=load_midi(source_path);before=load_midi(source_path);kind=detect_content_type_details(mid,content_type)['content_type'];registry=registry or ProfileRegistry();contexts=build_contexts(mid,registry,kind);notes=extract_notes(mid)
    end_tick=max((sum(int(msg.time) for msg in track) for track in mid.tracks),default=max(1,mid.ticks_per_beat*4));bars=_build_bar_spans(mid,end_tick);starts=[bar['start_tick'] for bar in bars];by_bar=defaultdict(list)
    for note in notes:by_bar[max(0,min(len(bars)-1,bisect_right(starts,int(note.onset))-1))].append(note)
    inferred={index:_infer_source_chord([note for note in rows if policy_for(getattr(contexts.get((note.track_index,note.channel)),'family','UNKNOWN')).get('policy_family') in TONAL_FAMILIES]) for index,rows in by_bar.items()}
    config=OptimizeConfig.for_mode('max');changes=[];protected=Counter();family_changes=Counter();chord_changes=Counter();occupied=defaultdict(list);collision_preserved=0
    for note in sorted(notes,key=lambda row:(row.onset,row.track_index,row.channel,row.note,row.occurrence)):
        ctx=contexts.get((note.track_index,note.channel));policy=policy_for(getattr(ctx,'family','UNKNOWN'));family=policy.get('policy_family','UNKNOWN')
        if not ctx or family not in TONAL_FAMILIES:
            protected['NON_TONAL_OR_UNKNOWN']+=1;occupied[(note.track_index,note.channel,note.note)].append((note.onset,note.off,note.note));continue
        if not include_solo and (family in LEAD_FAMILIES or any(word in str(ctx.role).upper() for word in ('SOLO','LEAD','COUNTER'))):
            protected['SOLO_DISABLED']+=1;occupied[(note.track_index,note.channel,note.note)].append((note.onset,note.off,note.note));continue
        profile=None;manual=None
        if not ctx.identity.conflict:
            profile,_status=registry.resolve_identity(ctx.identity.msb,ctx.identity.lsb,ctx.identity.program,ctx.role)
            manual=registry.resolve_manual_dnc(ctx.identity.msb,ctx.identity.lsb,ctx.identity.program)
        is_protected,reason=protect_note(note,ctx,profile,config,manual_dnc=manual)
        if is_protected:
            protected[reason or 'RX_DNC_GUARD']+=1;occupied[(note.track_index,note.channel,note.note)].append((note.onset,note.off,note.note));continue
        bar_index=max(0,min(len(bars)-1,bisect_right(starts,int(note.onset))-1));target=chords[bar_index%len(chords)];source=_style_source_chord(ctx) if kind=='style' else inferred.get(bar_index) or _infer_source_chord([])
        role_and_sound=str(ctx.role or '')+' '+str(ctx.identity.name or '');proposal=_degree_map(note.note,source,target,family,role_and_sound);proposal,collision=_collision_safe_pitch(proposal,note,target,family,occupied,role_and_sound)
        if collision:collision_preserved+=1
        occupied[(note.track_index,note.channel,proposal)].append((note.onset,note.off,note.note))
        if proposal==note.note:continue
        old=int(note.note);mid.tracks[note.track_index][note.on_index]=mid.tracks[note.track_index][note.on_index].copy(note=proposal);mid.tracks[note.track_index][note.off_index]=mid.tracks[note.track_index][note.off_index].copy(note=proposal)
        changes.append({'track':note.track_index,'channel':note.channel+1,'on_index':note.on_index,'off_index':note.off_index,'occurrence':note.occurrence,'old':old,'new':proposal,'onset':note.onset,'off':note.off,'bar':bar_index+1,'target_chord':target['label'],'source_chord':source['label'],'family':family,'role':role_and_sound,'reason':'FACTORY_GOLD_TEMPLATE_CHORD_DEGREE_REVOICE'})
        family_changes[family]+=1;chord_changes[target['label']]+=1
    target_path.parent.mkdir(parents=True,exist_ok=True);temporary=target_path.with_suffix(target_path.suffix+'.pattern.tmp')
    save_midi(mid,temporary);persisted=load_midi(temporary);verifier=validate_generated_pattern(before,persisted,changes,chords)
    if not verifier['pass']:
        try:temporary.unlink()
        except OSError:pass
        raise RuntimeError('CHORD_PATTERN_VERIFY_BLOCKED: '+json.dumps(verifier,ensure_ascii=False,sort_keys=True))
    temporary.replace(target_path)
    report={'schema':GENERATOR_SCHEMA,'input':str(source_path),'output':str(target_path),'content_type':kind,'mode':'EXPLICIT_RETRIEVAL_REVOICE','authority':{'factory':'PA800_STRUCTURE_SOUND_RX_DNC_AND_TEMPLATE','gold':'PERFORMANCE_TEMPLATE_EVIDENCE','generator':'PITCH_ONLY_CHORD_DEGREE_MAPPING','neural':'NOT_USED_NO_RETRAIN','velocity':'SOURCE_PROFILE_PERFORMANCE_PRESERVED'},'progression':[row['label'] for row in chords],'bars':len(bars),'progression_cycle':len(chords)!=len(bars),'include_solo':bool(include_solo),'changes':changes,'summary':{'notes_total':len(notes),'pitch_changed_notes':len(changes),'protected_notes':sum(protected.values()),'protected_reasons':dict(sorted(protected.items())),'changes_by_family':dict(sorted(family_changes.items())),'changes_by_chord':dict(sorted(chord_changes.items())),'collision_preserved':collision_preserved,'velocity_changes':0,'timing_changes':0,'gate_changes':0,'controller_changes':0,'sound_changes':0},'bar_plan':[{'bar':bar['index']+1,'meter':'%d/%d'%(bar['numerator'],bar['denominator']),'start_tick':bar['start_tick'],'end_tick':bar['end_tick'],'target_chord':chords[bar['index']%len(chords)]['label']} for bar in bars],'verifier':verifier}
    report_path=target_path.with_suffix(target_path.suffix+'.pattern.json');report_tmp=report_path.with_suffix(report_path.suffix+'.tmp');report_tmp.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8');report_tmp.replace(report_path);report['report_path']=str(report_path)
    return report
