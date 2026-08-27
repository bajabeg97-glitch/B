from types import SimpleNamespace
import mido

from pa800_optimizer.analysis.factory_usage import build_factory_usage_meter
from pa800_optimizer.config import OptimizeConfig
from pa800_optimizer.engines.velocity import optimize_velocity
from pa800_optimizer.engines.velocity_conductor import normalize_velocity
from pa800_optimizer.models import Change,NoteEvent,SoundIdentity,TrackContext
from pa800_optimizer.safety.rx_dnc import protect_note


def context(family,name='Rare Voice'):
    identity=SoundIdentity(121,0,10,name,family=family)
    return TrackContext(0,0,'SONG',identity,family=family)


def notes():
    return [NoteEvent(0,0,60+i,40+i*5,i*96,i*96+48,i*2,i*2+1,occurrence=0) for i in range(4)]


def midi_for(notes_):
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track)
    for index,note in enumerate(notes_):track.append(mido.Message('note_on',channel=0,note=note.note,velocity=note.velocity,time=0 if index==0 else 48));track.append(mido.Message('note_off',channel=0,note=note.note,velocity=0,time=48))
    return mid


class RegistryStub:
    def velocity_family_profile(self,*_args):return {'velocity':{'ideal_center':100},'_velocity_basis':'FACTORY_FAMILY_AGGREGATE'}
    def resolve_drum_key(self,*_args):return None
    def resolve_manual_dnc(self,*_args):return None


def weak_profile():
    return {'support':{'grade':'FALLBACK'},'_profile_stability':'UNKNOWN','velocity':{'working_min':80,'ideal_min':90,'ideal_center':100,'ideal_max':110,'working_max':120,'p05':70,'p95':125}}


def test_weak_exact_rare_profile_cannot_mutate_velocity():
    arr=notes();mid=midi_for(arr);ctx=context('ETHNIC');report=SimpleNamespace(changes=[]);config=OptimizeConfig.for_mode('live');config.velocity_random_strength=0
    optimize_velocity(mid,arr,{(0,0):ctx},{(0,0):weak_profile()},RegistryStub(),config,report)
    assert not report.changes


def test_rare_family_never_uses_family_velocity_fallback():
    arr=notes();mid=midi_for(arr);ctx=context('SYNTH_LEAD');report=SimpleNamespace(changes=[]);config=OptimizeConfig.for_mode('live')
    normalize_velocity(mid,arr,{(0,0):ctx},{(0,0):None},RegistryStub(),config,report)
    assert report.velocity_conductor['processed_contexts']==0 and not report.changes


def test_usage_meter_marks_weak_exact_evidence_blocked_and_detects_illegal_change():
    arr=notes();ctx=context('ETHNIC');config=OptimizeConfig.for_mode('live');profiles={(0,0):weak_profile()};contexts={(0,0):ctx};registry=RegistryStub()
    meter=build_factory_usage_meter(arr,contexts,profiles,registry,[],config)
    assert meter['pass'] and meter['stage_counts']['blocked']==4 and meter['stage_counts']['used']==0
    illegal=[Change(0,0,'velocity',40,80,'illegal',channel=0,note=60,occurrence=0)]
    assert not build_factory_usage_meter(arr,contexts,profiles,registry,illegal,config)['pass']


def test_sfx_and_cycle_random_names_are_always_note_protected():
    config=OptimizeConfig.for_mode('live');item=notes()[0]
    assert protect_note(item,context('SFX','Stadium'),None,config)[0]
    assert protect_note(item,context('SYNTH_LEAD','Wave Cycle Random'),None,config)[0]