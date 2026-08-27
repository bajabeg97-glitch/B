from types import SimpleNamespace
import mido

from pa800_optimizer.config import OptimizeConfig
from pa800_optimizer.engines.gate import optimize_gate
from pa800_optimizer.engines.timing import optimize_timing
from pa800_optimizer.engines.velocity import optimize_velocity
from pa800_optimizer.models import NoteEvent,SoundIdentity,TrackContext
from pa800_optimizer.safety.rx_dnc import protect_note


class RegistryStub:
    def resolve_drum_key(self,*_args):return None


class PositiveRegistryStub(RegistryStub):
    def instrument_positive_model_allowed(self,*_args):return True


def profile():
    return {'timing_residual_ticks':{'grid_1_32_24':{'working_min':-4,'working_max':4}},'gate_to_next_onset':{'ideal_center':.8,'working_min':.6,'working_max':1.0}}


def context(track,channel,family,role):
    return TrackContext(track,channel,role,SoundIdentity(121,0,0,family,family=family),family=family)


def note(track,channel,pitch,onset,off,on_index=0,off_index=1):
    return NoteEvent(track,channel,pitch,80,onset,off,on_index,off_index)


def track_with_note(channel,pitch,onset=10,duration=10):
    track=mido.MidiTrack();track.append(mido.Message('note_on',channel=channel,note=pitch,velocity=80,time=onset));track.append(mido.Message('note_off',channel=channel,note=pitch,velocity=0,time=duration));track.append(mido.MetaMessage('end_of_track',time=10));return track


def test_bass_timing_follows_nearest_drum_shift(monkeypatch):
    mid=mido.MidiFile(type=1,ticks_per_beat=192);mid.tracks.extend([track_with_note(9,36),track_with_note(8,40)])
    notes=[note(0,9,36,10,20),note(1,8,40,10,20)];contexts={(0,9):context(0,9,'DRUM_KIT','DRUM'),(1,8):context(1,8,'BASS','BASS')};profiles={(0,9):profile(),(1,8):profile()}
    monkeypatch.setattr('pa800_optimizer.engines.timing.stable_seed',lambda *args:args[3]);monkeypatch.setattr('pa800_optimizer.engines.timing.deterministic_gauss',lambda seed,_mean,_sigma:2 if seed==9 else -2)
    config=OptimizeConfig.for_mode('live');config.timing_strength=1.0;report=SimpleNamespace(changes=[])
    optimize_timing(mid,notes,contexts,profiles,PositiveRegistryStub(),config,report)
    assert notes[0].onset==12 and notes[1].onset==12
    assert any(change.reason.startswith('drum_anchor_timing:') for change in report.changes if change.note==40)


def test_piano_gate_is_not_rewritten_while_damper_is_held():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track)
    track.extend([mido.Message('control_change',channel=0,control=64,value=127,time=0),mido.Message('note_on',channel=0,note=60,velocity=80,time=0),mido.Message('note_off',channel=0,note=60,velocity=0,time=48),mido.Message('note_on',channel=0,note=64,velocity=80,time=48),mido.Message('note_off',channel=0,note=64,velocity=0,time=48),mido.Message('control_change',channel=0,control=64,value=0,time=0)])
    notes=[note(0,0,60,0,48,1,2),note(0,0,64,96,144,3,4)];contexts={(0,0):context(0,0,'PIANO','SONG')};report=SimpleNamespace(changes=[]);config=OptimizeConfig.for_mode('live');config.gate_strength=1.0
    optimize_gate(mid,notes,contexts,{(0,0):profile()},config,report)
    assert [item.off for item in notes]==[48,144]
    assert not report.changes


def test_long_string_tail_is_not_rewritten():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);mid.tracks.append(track_with_note(0,60,onset=0,duration=192));mid.tracks[0].append(mido.Message('note_on',channel=0,note=64,velocity=80,time=0));mid.tracks[0].append(mido.Message('note_off',channel=0,note=64,velocity=0,time=48))
    notes=[note(0,0,60,0,192,0,1),note(0,0,64,192,240,3,4)];contexts={(0,0):context(0,0,'STRINGS','SONG')};report=SimpleNamespace(changes=[]);config=OptimizeConfig.for_mode('live');config.gate_strength=1.0
    optimize_gate(mid,notes,contexts,{(0,0):profile()},config,report)
    assert notes[0].off==192


def test_brass_with_modulation_controller_skips_timing_and_gate(monkeypatch):
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track);track.extend([mido.Message('control_change',channel=0,control=1,value=90,time=0),mido.Message('note_on',channel=0,note=60,velocity=80,time=10),mido.Message('note_off',channel=0,note=60,velocity=0,time=48),mido.Message('note_on',channel=0,note=62,velocity=80,time=48),mido.Message('note_off',channel=0,note=62,velocity=0,time=48)])
    notes=[note(0,0,60,10,58,1,2),note(0,0,62,106,154,3,4)];contexts={(0,0):context(0,0,'BRASS','SONG')};profiles={(0,0):profile()};report=SimpleNamespace(changes=[]);config=OptimizeConfig.for_mode('live');config.timing_strength=1.0;config.gate_strength=1.0
    monkeypatch.setattr('pa800_optimizer.engines.timing.deterministic_gauss',lambda *_args:3)
    optimize_timing(mid,notes,contexts,profiles,RegistryStub(),config,report);optimize_gate(mid,notes,contexts,profiles,config,report)
    assert [(item.onset,item.off) for item in notes]==[(10,58),(106,154)]
    assert not report.changes


def test_overlapping_same_pitch_occurrences_skip_timing_and_gate(monkeypatch):
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track)
    track.extend([mido.Message('note_on',channel=0,note=60,velocity=80,time=10),mido.Message('note_on',channel=0,note=60,velocity=82,time=2),mido.Message('note_off',channel=0,note=60,velocity=0,time=20),mido.Message('note_off',channel=0,note=60,velocity=0,time=20),mido.Message('note_on',channel=0,note=64,velocity=80,time=40),mido.Message('note_off',channel=0,note=64,velocity=0,time=20)])
    notes=[note(0,0,60,10,32,0,2),note(0,0,60,12,52,1,3),note(0,0,64,92,112,4,5)];notes[1].occurrence=1
    contexts={(0,0):context(0,0,'ORGAN','SONG')};profiles={(0,0):profile()};report=SimpleNamespace(changes=[]);config=OptimizeConfig.for_mode('live');config.timing_strength=1.0;config.gate_strength=1.0
    monkeypatch.setattr('pa800_optimizer.engines.timing.deterministic_gauss',lambda *_args:3)
    optimize_timing(mid,notes,contexts,profiles,RegistryStub(),config,report);optimize_gate(mid,notes,contexts,profiles,config,report)
    assert [(item.onset,item.off) for item in notes[:2]]==[(10,32),(12,52)]
    assert not any(change.note==60 and change.kind in ('timing','gate') for change in report.changes)


def test_organ_legato_note_skips_timing(monkeypatch):
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track)
    track.extend([mido.Message('note_on',channel=0,note=60,velocity=80,time=10),mido.Message('note_off',channel=0,note=60,velocity=0,time=100),mido.Message('note_on',channel=0,note=62,velocity=80,time=-10),mido.Message('note_off',channel=0,note=62,velocity=0,time=50)])
    notes=[note(0,0,60,10,110,0,1),note(0,0,62,100,150,2,3)];contexts={(0,0):context(0,0,'ORGAN','SONG')};profiles={(0,0):profile()};report=SimpleNamespace(changes=[]);config=OptimizeConfig.for_mode('live');config.timing_strength=1.0
    monkeypatch.setattr('pa800_optimizer.engines.timing.deterministic_gauss',lambda *_args:-4)
    optimize_timing(mid,notes,contexts,profiles,RegistryStub(),config,report)
    assert [(item.onset,item.off) for item in notes]==[(10,110),(100,150)]


def test_gate_does_not_extend_note_past_next_same_pitch_onset():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track)
    track.extend([mido.Message('note_on',channel=0,note=60,velocity=80,time=0),mido.Message('note_off',channel=0,note=60,velocity=0,time=20),mido.Message('note_on',channel=0,note=64,velocity=80,time=20),mido.Message('note_off',channel=0,note=64,velocity=0,time=10),mido.Message('note_on',channel=0,note=60,velocity=80,time=10),mido.Message('note_off',channel=0,note=60,velocity=0,time=20),mido.MetaMessage('end_of_track',time=100)])
    notes=[note(0,0,60,0,20,0,1),note(0,0,64,40,50,2,3),note(0,0,60,60,80,4,5)];notes[2].occurrence=1
    contexts={(0,0):context(0,0,'GUITAR','SONG')};report=SimpleNamespace(changes=[]);config=OptimizeConfig.for_mode('live');config.gate_strength=1.0
    long_profile={'gate_to_next_onset':{'ideal_center':1.8,'working_min':1.8,'working_max':1.8}}
    optimize_gate(mid,notes,contexts,{(0,0):long_profile},config,report)
    assert notes[0].off<=notes[2].onset


def test_timing_preserves_legal_zero_duration_drum_one_shot(monkeypatch):
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track)
    track.extend([mido.Message('note_on',channel=9,note=36,velocity=110,time=10),mido.Message('note_off',channel=9,note=36,velocity=0,time=0),mido.MetaMessage('end_of_track',time=20)])
    notes=[note(0,9,36,10,10,0,1)];contexts={(0,9):context(0,9,'DRUM_KIT','DRUM')};profiles={(0,9):profile()};report=SimpleNamespace(changes=[]);config=OptimizeConfig.for_mode('live');config.timing_strength=1.0
    monkeypatch.setattr('pa800_optimizer.engines.timing.deterministic_gauss',lambda *_args:2)
    optimize_timing(mid,notes,contexts,profiles,RegistryStub(),config,report)
    assert notes[0].onset==notes[0].off


def test_guitar_strum_receives_one_coherent_factory_timing_shift(monkeypatch):
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track)
    track.extend([mido.Message('note_on',channel=0,note=60,velocity=70,time=10),mido.Message('note_on',channel=0,note=64,velocity=80,time=2),mido.Message('note_off',channel=0,note=60,velocity=0,time=20),mido.Message('note_off',channel=0,note=64,velocity=0,time=0),mido.MetaMessage('end_of_track',time=20)])
    notes=[note(0,0,60,10,32,0,2),note(0,0,64,12,32,1,3)];contexts={(0,0):context(0,0,'GUITAR','SONG')};report=SimpleNamespace(changes=[]);config=OptimizeConfig.for_mode('live');config.timing_strength=1.0
    monkeypatch.setattr('pa800_optimizer.engines.timing.stable_seed',lambda *args:args[-3]);monkeypatch.setattr('pa800_optimizer.engines.timing.deterministic_gauss',lambda seed,*_args:3 if seed==60 else -3)
    optimize_timing(mid,notes,contexts,{(0,0):profile()},PositiveRegistryStub(),config,report)
    assert notes[1].onset-notes[0].onset==2
    assert notes[0].onset!=10 and notes[1].onset!=12
    assert all(change.reason.startswith('coherent_strum_timing:') for change in report.changes)


def test_piano_chord_velocity_moves_as_one_shape(monkeypatch):
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track);velocities=(40,60,80,100);notes=[]
    for index,(pitch,velocity) in enumerate(zip((60,64,67,72),velocities)):
        track.append(mido.Message('note_on',channel=0,note=pitch,velocity=velocity,time=0));track.append(mido.Message('note_off',channel=0,note=pitch,velocity=0,time=96));notes.append(NoteEvent(0,0,pitch,velocity,0,96,index*2,index*2+1))
    p=profile();p['velocity']={'working_min':50,'ideal_min':65,'ideal_center':85,'ideal_max':105,'working_max':115,'p05':1,'p95':127}
    contexts={(0,0):context(0,0,'PIANO','SONG')};config=OptimizeConfig.for_mode('max');config.velocity_strength=1.0;report=SimpleNamespace(changes=[])
    monkeypatch.setattr('pa800_optimizer.engines.velocity.deterministic_gauss',lambda *_args:4)
    optimize_velocity(mid,notes,contexts,{(0,0):p},PositiveRegistryStub(),config,report)
    after=[item.velocity for item in notes]
    assert [b-a for a,b in zip(velocities,after)]==[after[0]-velocities[0]]*4
    assert [after[i+1]-after[i] for i in range(3)]==[20,20,20]
    assert all('coherent_chord_velocity' in change.reason for change in report.changes)


def test_ensemble_chord_receives_one_coherent_timing_shift(monkeypatch):
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track)
    for pitch in (60,64,67):track.append(mido.Message('note_on',channel=0,note=pitch,velocity=80,time=0))
    for pitch in (60,64,67):track.append(mido.Message('note_off',channel=0,note=pitch,velocity=0,time=96 if pitch==60 else 0))
    track.append(mido.MetaMessage('end_of_track',time=20))
    notes=[note(0,0,pitch,0,96,index,index+3) for index,pitch in enumerate((60,64,67))]
    contexts={(0,0):context(0,0,'ENSEMBLE','SONG')};config=OptimizeConfig.for_mode('live');config.timing_strength=1.0;report=SimpleNamespace(changes=[])
    monkeypatch.setattr('pa800_optimizer.engines.timing.deterministic_gauss',lambda *_args:3)
    optimize_timing(mid,notes,contexts,{(0,0):profile()},PositiveRegistryStub(),config,report)
    # Ensemble uses its conservative family scale while keeping every chord
    # member on one coherent onset.
    assert {item.onset for item in notes}=={1}
    assert all(change.reason.startswith('coherent_sustain_chord_timing:') for change in report.changes)


def test_ensemble_phrase_velocity_preserves_internal_contour(monkeypatch):
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track);velocities=(50,65,80,95);notes=[]
    for index,(pitch,velocity) in enumerate(zip((60,62,64,65),velocities)):
        track.append(mido.Message('note_on',channel=0,note=pitch,velocity=velocity,time=0 if index==0 else 48));track.append(mido.Message('note_off',channel=0,note=pitch,velocity=0,time=24));notes.append(NoteEvent(0,0,pitch,velocity,index*72,index*72+24,index*2,index*2+1))
    p=profile();p['velocity']={'working_min':60,'ideal_min':75,'ideal_center':90,'ideal_max':105,'working_max':115,'p05':1,'p95':127}
    contexts={(0,0):context(0,0,'ENSEMBLE','SONG')};config=OptimizeConfig.for_mode('max');config.velocity_strength=1.0;report=SimpleNamespace(changes=[])
    optimize_velocity(mid,notes,contexts,{(0,0):p},PositiveRegistryStub(),config,report)
    after=[item.velocity for item in notes]
    assert [after[index+1]-after[index] for index in range(3)]==[15,15,15]
    assert all('coherent_phrase_velocity' in change.reason for change in report.changes)


def test_reed_phrase_model_preserves_velocity_when_expression_controller_exists():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track);track.append(mido.Message('control_change',channel=0,control=1,value=90,time=0));notes=[]
    for index,pitch in enumerate((60,62,64,65)):
        track.append(mido.Message('note_on',channel=0,note=pitch,velocity=60+index*10,time=48));track.append(mido.Message('note_off',channel=0,note=pitch,velocity=0,time=24));notes.append(NoteEvent(0,0,pitch,60+index*10,index*72+48,index*72+72,index*2+1,index*2+2))
    p=profile();p['velocity']={'working_min':80,'ideal_min':90,'ideal_center':100,'ideal_max':110,'working_max':120,'p05':1,'p95':127}
    contexts={(0,0):context(0,0,'REED','SONG')};config=OptimizeConfig.for_mode('max');config.velocity_strength=1.0;report=SimpleNamespace(changes=[])
    optimize_velocity(mid,notes,contexts,{(0,0):p},PositiveRegistryStub(),config,report)
    assert [item.velocity for item in notes]==[60,70,80,90]
    assert not report.changes


def test_brass_velocity_preserves_recorded_modulation_expression():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track);track.append(mido.Message('control_change',channel=0,control=1,value=88,time=0));notes=[]
    for index,pitch in enumerate((60,62,64,67)):
        velocity=55+index*10;track.append(mido.Message('note_on',channel=0,note=pitch,velocity=velocity,time=48));track.append(mido.Message('note_off',channel=0,note=pitch,velocity=0,time=24));notes.append(NoteEvent(0,0,pitch,velocity,index*72+48,index*72+72,index*2+1,index*2+2))
    p=profile();p['velocity']={'working_min':80,'ideal_min':90,'ideal_center':100,'ideal_max':110,'working_max':120,'p05':1,'p95':127}
    contexts={(0,0):context(0,0,'BRASS','SONG')};config=OptimizeConfig.for_mode('max');config.velocity_strength=1.0;report=SimpleNamespace(changes=[])
    optimize_velocity(mid,notes,contexts,{(0,0):p},PositiveRegistryStub(),config,report)
    assert [item.velocity for item in notes]==[55,65,75,85]
    assert not report.changes


def test_guitar_exact_special_pitch_is_protected_without_rx_name():
    protected,reason=protect_note(note(0,0,24,0,48),context(0,0,'GUITAR','SONG'),{'special_pitch_candidates':[{'min':24,'max':24}]},OptimizeConfig.for_mode('max'))
    assert protected and reason=='instrument_special_pitch_candidate'
