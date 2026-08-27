import mido

from pa800_optimizer.config import OptimizeConfig
from pa800_optimizer.engines.velocity_conductor import normalize_velocity
from pa800_optimizer.models import NoteEvent,OptimizationReport,SoundIdentity,TrackContext


class Registry:
    def resolve_drum_key(self,*_args):return None
    def velocity_family_profile(self,*_args):return None


class FamilyFallbackRegistry(Registry):
    def velocity_family_profile(self,*_args):return profile(95)


def add_track(mid,velocities,channel=0):
    track=mido.MidiTrack();mid.tracks.append(track);notes=[]
    for i,velocity in enumerate(velocities):
        track.append(mido.Message('note_on',channel=channel,note=60+i,velocity=velocity,time=0));notes.append(NoteEvent(len(mid.tracks)-1,channel,60+i,velocity,i*100,i*100+80,i,i))
    return notes


def profile(center,lo=20,hi=120):return {'velocity':{'working_min':lo,'ideal_min':center-10,'ideal_center':center,'ideal_max':center+10,'working_max':hi}}


def test_different_instruments_receive_different_normal_centers():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);a=add_track(mid,[65,75,85,95]);b=add_track(mid,[65,75,85,95])
    notes=a+b;contexts={(0,0):TrackContext(0,0,'ACC1',SoundIdentity(1,1,1,'Soft Instrument','PIANO'),family='PIANO'),(1,0):TrackContext(1,0,'ACC1',SoundIdentity(1,1,2,'Loud Instrument','BRASS'),family='BRASS')}
    profiles={(0,0):profile(70),(1,0):profile(95)};report=OptimizationReport('in','out');cfg=OptimizeConfig.for_mode('live')
    normalize_velocity(mid,notes,contexts,profiles,Registry(),cfg,report)
    ma=sorted(n.velocity for n in a)[2];mb=sorted(n.velocity for n in b)[2]
    assert mb-ma>=15
    assert report.velocity_conductor['processed_contexts']==2


def test_conductor_preserves_internal_dynamic_distances():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);notes=add_track(mid,[50,60,70,80])
    ctx=TrackContext(0,0,'ACC1',SoundIdentity(1,1,1,'Instrument','PIANO'),family='PIANO');report=OptimizationReport('in','out')
    before=[n.velocity for n in notes];normalize_velocity(mid,notes,{(0,0):ctx},{(0,0):profile(90)},Registry(),OptimizeConfig.for_mode('live'),report);after=[n.velocity for n in notes]
    assert [b-a for a,b in zip(before[1:],before)]==[b-a for a,b in zip(after[1:],after)]


def test_protected_note_velocity_is_untouched():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);notes=add_track(mid,[15,50,60,70,80]);notes[0].protected=True
    ctx=TrackContext(0,0,'ACC1',SoundIdentity(1,1,1,'RX Instrument','GUITAR',True),family='GUITAR');report=OptimizationReport('in','out')
    normalize_velocity(mid,notes,{(0,0):ctx},{(0,0):profile(90)},Registry(),OptimizeConfig.for_mode('max'),report)
    assert mid.tracks[0][0].velocity==15


def test_cc7_cc11_affect_energy_report_but_are_not_rewritten():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track);track.append(mido.Message('control_change',channel=0,control=7,value=55,time=0));track.append(mido.Message('control_change',channel=0,control=11,value=80,time=0));notes=[]
    for i,velocity in enumerate([60,70,80,90]):
        index=len(track);track.append(mido.Message('note_on',channel=0,note=60+i,velocity=velocity,time=0));notes.append(NoteEvent(0,0,60+i,velocity,i*100,i*100+80,index,index))
    ctx=TrackContext(0,0,'SONG',SoundIdentity(1,1,1,'Instrument','PIANO'),family='PIANO');report=OptimizationReport('in','out');before=[(m.control,m.value) for m in track if m.type=='control_change']
    normalize_velocity(mid,notes,{(0,0):ctx},{(0,0):profile(90)},Registry(),OptimizeConfig.for_mode('live'),report)
    row=report.velocity_conductor['contexts'][0];after=[(m.control,m.value) for m in track if m.type=='control_change']
    assert row['controller_energy_scale']<1 and row['effective_energy_before']<row['normalized_median_before']
    assert before==after and report.velocity_conductor['controllers_rewritten'] is False


def test_dynamic_iqr_retention_gate_is_reported():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);notes=add_track(mid,[20,40,80,120]);ctx=TrackContext(0,0,'SONG',SoundIdentity(1,1,1,'Instrument','PIANO'),family='PIANO');report=OptimizationReport('in','out');cfg=OptimizeConfig.for_mode('max')
    normalize_velocity(mid,notes,{(0,0):ctx},{(0,0):profile(90,40,100)},Registry(),cfg,report)
    assert report.velocity_conductor['contexts'][0]['iqr_retention']>=cfg.velocity_min_iqr_retention


def test_organ_family_cap_wins_over_distant_profile_rails():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);notes=add_track(mid,[30,35,40,45]);before=[note.velocity for note in notes]
    ctx=TrackContext(0,0,'SONG',SoundIdentity(1,1,16,'Organ','ORGAN'),family='ORGAN');report=OptimizationReport('in','out');cfg=OptimizeConfig.for_mode('max')
    normalize_velocity(mid,notes,{(0,0):ctx},{(0,0):profile(110,100,127)},Registry(),cfg,report)
    assert all(abs(note.velocity-old)<=4 for note,old in zip(notes,before))


def test_factory_data_only_mode_rejects_family_velocity_fallback():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);notes=add_track(mid,[50,60,70,80]);before=[note.velocity for note in notes]
    ctx=TrackContext(0,0,'SONG',SoundIdentity(1,1,1,'Unknown Exact','PIANO'),family='PIANO');report=OptimizationReport('in','out');cfg=OptimizeConfig.for_mode('live')
    normalize_velocity(mid,notes,{(0,0):ctx},{},FamilyFallbackRegistry(),cfg,report)
    assert [note.velocity for note in notes]==before and report.velocity_conductor['processed_contexts']==0