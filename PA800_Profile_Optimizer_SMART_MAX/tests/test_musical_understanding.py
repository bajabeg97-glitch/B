import mido
import json

from pa800_optimizer.analysis.context import build_contexts
from pa800_optimizer.analysis.musical_context import analyze_musical_context
from pa800_optimizer.analysis.musical_understanding import analyze_musical_understanding
from pa800_optimizer.core.midi_io import extract_notes
from pa800_optimizer.profiles.registry import ProfileRegistry
from pa800_optimizer.understanding_cli import analyze_file,render_markdown


def _track(name,channel,program,notes,lsb=0,msb=0):
    track=mido.MidiTrack();track.extend([mido.MetaMessage('track_name',name=name,time=0),mido.Message('control_change',channel=channel,control=0,value=msb,time=0),mido.Message('control_change',channel=channel,control=32,value=lsb,time=0),mido.Message('program_change',channel=channel,program=program,time=0)])
    first=True
    for pitch,velocity,onset_gap,duration in notes:
        track.append(mido.Message('note_on',channel=channel,note=pitch,velocity=velocity,time=0 if first else onset_gap));track.append(mido.Message('note_off',channel=channel,note=pitch,velocity=0,time=duration));first=False
    return track


def _analyze(mid):
    registry=ProfileRegistry();contexts=build_contexts(mid,registry,'song');notes=extract_notes(mid);context=analyze_musical_context(mid,notes,contexts,'song')
    return analyze_musical_understanding(mid,notes,contexts,context)


def test_understanding_describes_functions_phrases_and_never_grants_authority():
    mid=mido.MidiFile(type=1,ticks_per_beat=192)
    mid.tracks.append(_track('Drums',9,0,[(36,110,96,48)]*8,msb=120))
    mid.tracks.append(_track('Bass',1,33,[(36,72+i*2,48,48) for i in range(8)]))
    mid.tracks.append(_track('Lead Melody',0,73,[(72+i%3,65+i*4,96,72) for i in range(8)]))
    result=_analyze(mid)
    assert result['schema']=='PA800_MUSICAL_UNDERSTANDING_V2'
    assert result['analyzer_only'] and result['mutations']==0 and not result['authority_granted']
    assert any(row['function']=='FOUNDATION_DRUM' for row in result['track_narratives'])
    assert any(row['function']=='FOUNDATION_BASS' for row in result['track_narratives'])
    assert any(row['phrases'] for row in result['track_narratives'])
    assert result['groove']['relationships']
    assert all(not row['apply_authority'] for row in result['suggestions'])


def test_simultaneous_chord_is_named_but_tonal_center_stays_unknown_without_support():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track)
    track.extend([mido.MetaMessage('track_name',name='Piano Comp',time=0),mido.Message('program_change',channel=0,program=0,time=0),mido.Message('note_on',channel=0,note=60,velocity=70,time=0),mido.Message('note_on',channel=0,note=64,velocity=74,time=0),mido.Message('note_on',channel=0,note=67,velocity=78,time=0),mido.Message('note_off',channel=0,note=60,velocity=0,time=192),mido.Message('note_off',channel=0,note=64,velocity=0,time=0),mido.Message('note_off',channel=0,note=67,velocity=0,time=0)])
    result=_analyze(mid)
    assert any(row['label']=='C_MAJOR' for row in result['harmony']['simultaneous_chords'])
    assert result['harmony']['tonal_center']['status']=='UNKNOWN'
    assert any(row['domain']=='harmony' for row in result['uncertainties'])


def test_sparse_unknown_track_is_not_forced_into_a_confident_musical_role():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track)
    track.extend([mido.MetaMessage('track_name',name='Mystery',time=0),mido.Message('note_on',channel=0,note=60,velocity=64,time=0),mido.Message('note_off',channel=0,note=60,velocity=0,time=24)])
    result=_analyze(mid);narrative=result['track_narratives'][0]
    assert narrative['function_confidence']<.8
    assert result['harmony']['tonal_center']['status']=='UNKNOWN'
    assert result['mutations']==0


def test_analysis_only_cli_report_does_not_create_or_modify_midi(tmp_path):
    source=tmp_path/'song.mid';mid=mido.MidiFile(type=1,ticks_per_beat=192);mid.tracks.append(_track('Lead Melody',0,73,[(72,70,96,72)]*6));mid.save(source);before=source.read_bytes()
    result=analyze_file(str(source),'song');report=tmp_path/'music.json';report.write_text(json.dumps(result),encoding='utf-8')
    assert source.read_bytes()==before
    assert result['mutations']==0 and result['musical_understanding']['authority_granted'] is False
    assert json.loads(report.read_text())['schema']=='PA800_MUSIC_ANALYSIS_REPORT_V1'
    markdown=render_markdown(result)
    assert '# Muzičko razumijevanje' in markdown and '## UNKNOWN i granice dokaza' in markdown
    assert source.read_bytes()==before


def test_near_onset_arpeggio_is_grouped_and_voice_leading_is_described():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track)
    track.extend([mido.MetaMessage('track_name',name='Piano Comp',time=0),mido.Message('program_change',channel=0,program=0,time=0)])
    for pitch,delay in ((60,0),(64,4),(67,4)):track.append(mido.Message('note_on',channel=0,note=pitch,velocity=72,time=delay))
    for pitch,delay in ((60,184),(64,0),(67,0)):track.append(mido.Message('note_off',channel=0,note=pitch,velocity=0,time=delay))
    for pitch,delay in ((62,192),(65,4),(69,4)):track.append(mido.Message('note_on',channel=0,note=pitch,velocity=74,time=delay))
    for pitch,delay in ((62,184),(65,0),(69,0)):track.append(mido.Message('note_off',channel=0,note=pitch,velocity=0,time=delay))
    result=_analyze(mid);chords=result['harmony']['simultaneous_chords']
    assert chords[0]['label']=='C_MAJOR' and chords[0]['grouping']=='NEAR_ONSET_CLUSTER'
    assert chords[1]['label']=='D_MINOR' and result['harmony']['voice_leading']
    assert result['harmony']['harmonic_rhythm_median_beats'] is not None


def test_alternating_foreground_parts_are_only_call_response_candidates():
    mid=mido.MidiFile(type=1,ticks_per_beat=192)
    a=mido.MidiTrack();b=mido.MidiTrack();mid.tracks.extend([a,b])
    a.extend([mido.MetaMessage('track_name',name='Lead Melody A',time=0),mido.Message('program_change',channel=0,program=73,time=0)])
    b.extend([mido.MetaMessage('track_name',name='Lead Melody B',time=0),mido.Message('program_change',channel=1,program=71,time=0)])
    for _ in range(4):a.extend([mido.Message('note_on',channel=0,note=72,velocity=76,time=0 if len(a)==2 else 336),mido.Message('note_off',channel=0,note=72,velocity=0,time=48)])
    b.extend([mido.Message('note_on',channel=1,note=76,velocity=74,time=192),mido.Message('note_off',channel=1,note=76,velocity=0,time=48)])
    for _ in range(3):b.extend([mido.Message('note_on',channel=1,note=76,velocity=74,time=336),mido.Message('note_off',channel=1,note=76,velocity=0,time=48)])
    result=_analyze(mid);relations=result['interaction']['relationships']
    assert relations and relations[0]['relationship']=='CALL_RESPONSE_CANDIDATE'
    assert 'not proof' in relations[0]['limitation']
    assert any(row['action']=='PRESERVE_ALTERNATING_SPACE' and not row['apply_authority'] for row in result['suggestions'])


def test_arrangement_exposes_bounded_tension_trajectory():
    mid=mido.MidiFile(type=1,ticks_per_beat=192)
    mid.tracks.append(_track('Bass',1,33,[(36,60,48,48)]*12))
    mid.tracks.append(_track('Lead Melody',0,73,[(72+i%4,65+i,48,48) for i in range(12)]))
    result=_analyze(mid);sections=result['arrangement']['sections']
    assert sections and all(0<=row['tension_proxy']<=1 for row in sections)
    assert all(row['trajectory_from_previous'] in ('START','BUILD','RELEASE','STABLE') for row in sections)