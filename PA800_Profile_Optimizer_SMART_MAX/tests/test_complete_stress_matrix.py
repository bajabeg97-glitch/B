import math
import struct
from pathlib import Path
from types import SimpleNamespace

import mido

from pa800_optimizer.analysis.instrument_fingerprints import audit_instrument_fingerprints,snapshot_instrument_state
from pa800_optimizer.analysis.factory_atomic import FactoryAtomicKnowledge
from pa800_optimizer.config import OptimizeConfig
from pa800_optimizer.core.midi_io import extract_notes
from pa800_optimizer.core.tolerant_factory_parser import read_vlq,scan_invalid_channel_events
from pa800_optimizer.manual import DncManualRegistry
from pa800_optimizer.optimizer import Optimizer
from pa800_optimizer.profiles.registry import ProfileRegistry
from pa800_optimizer.safety.rx_dnc import sensitive_controller
from pa800_optimizer.utils import deterministic_gauss,piecewise_map,quantiles,stable_seed
from tools.build_profile_completeness import build as build_completeness,render as render_completeness
from tools.compatibility_matrix import current_identity
from tools.pc_validation import make_midi
from tools.public_api_stress import build_manifest
from tools.run_process_certification import certify
from tools.release_audit import sha256


def test_public_api_inventory_exceeds_declared_235_by_65_and_has_no_gap():
    report=build_manifest();inventory=report['inventory']
    assert inventory['public_functions']>=235 and inventory['modules']>=65
    assert inventory['unclassified']==0
    assert len(report['functions'])==inventory['public_functions']
    assert all(row['coverage_mode'] and row['coverage_reason'] for row in report['functions'])
    assert {row['id'] for row in report['stress_scenarios']}=={'EXTREME_DOMAIN','DENSE_DETERMINISM','CORRELATION_BREAKERS','PROFILE_CROSSCHECK','FAIL_CLOSED_IO','INSTRUMENT_INTENT_V3','FAMILY_INTENT_V1','SECTION_NARRATIVE_V3','NEURAL_DATASET_V2','SELF_SUPERVISED_ENCODER_V1','EXACT_INSTRUMENT_PROFILES_V1'}


def _extreme_midi(path):
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track);track.append(mido.MetaMessage('track_name',name='Extreme 0-127',time=0))
    for channel in range(16):
        track.extend([mido.Message('control_change',channel=channel,control=0,value=0 if channel%2==0 else 127,time=0),mido.Message('control_change',channel=channel,control=32,value=127 if channel%2==0 else 0,time=0),mido.Message('program_change',channel=channel,program=0 if channel%2==0 else 127,time=0),mido.Message('control_change',channel=channel,control=1,value=0,time=0),mido.Message('control_change',channel=channel,control=2,value=127,time=0),mido.Message('control_change',channel=channel,control=64,value=127,time=0),mido.Message('control_change',channel=channel,control=80,value=0,time=0),mido.Message('control_change',channel=channel,control=81,value=127,time=0)])
        track.extend([mido.Message('note_on',channel=channel,note=0,velocity=1,time=0),mido.Message('note_off',channel=channel,note=0,velocity=0,time=0),mido.Message('note_on',channel=channel,note=127,velocity=127,time=1000000 if channel==15 else 1),mido.Message('note_off',channel=channel,note=127,velocity=0,time=1)])
    track.extend([mido.Message('control_change',channel=0,control=32,value=3,time=0),mido.Message('program_change',channel=0,program=1,time=0),mido.MetaMessage('end_of_track',time=0)]);mid.save(path)


def test_extreme_midi_domain_is_byte_identical_in_preserve(tmp_path):
    source=tmp_path/'extreme.mid';output=tmp_path/'extreme_out.mid';_extreme_midi(source)
    report=Optimizer(OptimizeConfig.for_mode('preserve')).optimize(source,output)
    assert source.read_bytes()==output.read_bytes()
    assert report.verifier['pass'] and report.quality_gate['pass']
    notes=extract_notes(mido.MidiFile(output));assert len(notes)==32
    assert min(note.note for note in notes)==0 and max(note.note for note in notes)==127
    assert min(note.velocity for note in notes)==1 and max(note.velocity for note in notes)==127
    assert any(note.duration==0 for note in notes)


def _dense_midi(path):
    mid=mido.MidiFile(type=1,ticks_per_beat=192)
    for channel in range(16):
        track=mido.MidiTrack();mid.tracks.append(track);track.extend([mido.MetaMessage('track_name',name=f'Song Layer {channel}',time=0),mido.Message('control_change',channel=channel,control=0,value=121,time=0),mido.Message('control_change',channel=channel,control=32,value=3,time=0),mido.Message('program_change',channel=channel,program=0,time=0),mido.Message('control_change',channel=channel,control=1,value=channel*8,time=0),mido.Message('control_change',channel=channel,control=64,value=127 if channel%2 else 0,time=0)])
        for index in range(32):
            track.append(mido.Message('note_on',channel=channel,note=36+(index*7+channel)%60,velocity=1+(index*17+channel*11)%127,time=0 if index==0 else (1 if index%3 else 96)))
            track.append(mido.Message('note_off',channel=channel,note=36+(index*7+channel)%60,velocity=0,time=0 if index%11==0 else 47))
    mid.save(path)


def _controller_signature(mid):
    return [(ti,msg.channel,msg.control,msg.value) for ti,track in enumerate(mid.tracks) for msg in track if msg.type=='control_change' and msg.control in (1,2,64,80,81)]


def test_dense_16_channel_run_is_deterministic_and_preserves_correlated_controllers(tmp_path):
    source=tmp_path/'dense.mid';first=tmp_path/'first.mid';second=tmp_path/'second.mid';_dense_midi(source);before=mido.MidiFile(source);before_notes=len(extract_notes(before));before_cc=_controller_signature(before)
    config=OptimizeConfig.for_mode('natural');config.content_type='song';one=Optimizer(config).optimize(source,first);two=Optimizer(config).optimize(source,second)
    assert first.read_bytes()==second.read_bytes()
    assert one.verifier['pass'] and two.verifier['pass'] and one.quality_gate['pass']
    after=mido.MidiFile(first);assert len(extract_notes(after))==before_notes==512
    after_cc=_controller_signature(after)
    assert all(event in after_cc for event in before_cc)
    added=[event for event in after_cc if event not in before_cc]
    assert added==[(channel,channel,64,0) for channel in range(1,16,2)]


def _note(channel,pitch,onset,off,velocity,occurrence=0):
    return SimpleNamespace(track_index=0,channel=channel,note=pitch,onset=onset,off=off,velocity=velocity,occurrence=occurrence)


def test_correlation_audit_detects_simultaneous_cross_family_regressions():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track);track.append(mido.Message('control_change',channel=4,control=1,value=80,time=0))
    notes=[_note(9,36,0,24,110),_note(8,40,0,96,85),_note(1,60,192,288,50),_note(1,64,192,288,80),_note(1,67,192,288,110),_note(2,55,384,768,70),_note(2,60,384,768,85),_note(3,60,768,900,70),_note(3,64,864,960,80),_note(4,67,960,1056,90)]
    contexts={(0,9):SimpleNamespace(family='DRUM_KIT'),(0,8):SimpleNamespace(family='BASS'),(0,1):SimpleNamespace(family='PIANO'),(0,2):SimpleNamespace(family='STRINGS'),(0,3):SimpleNamespace(family='ORGAN'),(0,4):SimpleNamespace(family='BRASS')}
    before=snapshot_instrument_state(mid,notes,contexts);notes[1].onset=80
    for item in notes[2:5]:item.velocity=80
    notes[5].off=500;notes[7].velocity=100;notes[7].off=850;mid.tracks[0][0]=mid.tracks[0][0].copy(value=20)
    result=audit_instrument_fingerprints(before,mid,notes,contexts)
    assert not result['pass']
    for key in ('bass_drum_lock_preserved','piano_chord_velocity_spread_retained','sustain_tails_not_shortened','organ_velocity_limited','organ_legato_preserved','expressive_controller_contours_preserved'):assert result['checks'][key] is False


def test_numeric_extremes_are_finite_monotonic_and_seed_decorrelated():
    assert quantiles([])==[0.0]*5 and quantiles([127])==[127.0]*5
    src=[0,0,64,127,127];dst=[1,20,64,110,127];mapped=[piecewise_map(value,src,dst) for value in range(128)]
    assert all(math.isfinite(value) for value in mapped) and all(a<=b for a,b in zip(mapped,mapped[1:]))
    a=[deterministic_gauss(stable_seed('A',index)) for index in range(512)];b=[deterministic_gauss(stable_seed('B',index)) for index in range(512)]
    mean_a=sum(a)/len(a);mean_b=sum(b)/len(b);num=sum((x-mean_a)*(y-mean_b) for x,y in zip(a,b));den=math.sqrt(sum((x-mean_a)**2 for x in a)*sum((y-mean_b)**2 for y in b));correlation=num/den
    assert abs(correlation)<.15


def test_read_only_knowledge_surfaces_cover_missing_cross_correlations():
    atomic=FactoryAtomicKnowledge()
    cross=atomic.cross_role('Variation 1','DRUM','ACC2')
    assert cross and cross['n']>0
    techniques=atomic.techniques_for(family='GUITAR')
    assert techniques and all(row['family']=='GUITAR' for row in techniques)
    dnc=DncManualRegistry();profile=dnc.data['sounds'][0]
    assert dnc.is_dnc(profile['msb'],profile['lsb'],profile['program'])
    states=dnc.state_semantics(profile,{'cc80':127,'cc81':127,'cc1':127,'cc2':127,'cc64':127,'aftertouch':127})
    assert set(states)<=set(('sc1_active','sc2_active','y_plus_active','y_minus_active','damper_active','aftertouch_active'))
    assert all(states.values())
    registry=ProfileRegistry()
    assert isinstance(registry.arranger_variation_progression(),dict)
    assert registry.family_fallback('GUITAR','ACC1') is None
    rx=SimpleNamespace(identity=SimpleNamespace(rx_named=True,dnc_named=False))
    plain=SimpleNamespace(identity=SimpleNamespace(rx_named=False,dnc_named=False))
    assert sensitive_controller(80,rx) and not sensitive_controller(80,plain) and not sensitive_controller(7,rx)


def test_tolerant_parser_detects_illegal_data_bytes_without_clipping(tmp_path):
    assert read_vlq(bytes((0x81,0x00)),0)==(128,2)
    body=bytes((0x00,0x90,0x00,0xff,0x00,0xff,0x2f,0x00))
    raw=b'MThd'+struct.pack('>IHHH',6,0,1,192)+b'MTrk'+struct.pack('>I',len(body))+body
    path=tmp_path/'illegal.mid';path.write_bytes(raw)
    assert scan_invalid_channel_events(path)==[(0,0x90,(0,255))]


def test_release_helpers_render_identity_fixture_and_process_contract(tmp_path):
    text=render_completeness(build_completeness())
    assert 'Complete cards: **565/565**' in text
    build_id,version=current_identity();assert len(build_id)==64 and version=='3.4.0a2'
    fixture=tmp_path/'pc_fixture.mid';make_midi(fixture,style=True,tracks=2,notes_per_track=4)
    assert len(extract_notes(mido.MidiFile(fixture)))==8
    assert len(sha256(fixture))==64
    report=certify(tmp_path/'process_certification',run_regression=False)
    assert report['pass'] and report['scenario_count']==52 and report['coverage']['passed_stages']==26

def test_complete_stress_runtime_suite_is_not_self_referential():
    from tools.run_complete_stress import _tests, META_RELEASE_TESTS
    tests=set(_tests())
    assert tests.isdisjoint(META_RELEASE_TESTS)
    assert 'tests/test_optimizer.py' in tests
