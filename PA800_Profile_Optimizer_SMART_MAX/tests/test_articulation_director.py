import copy
import os
import tempfile
import mido

from pa800_optimizer.analysis.context import build_contexts
from pa800_optimizer.analysis.dnc_state import build_controller_states
from pa800_optimizer.articulation_director import ArticulationDirector
from pa800_optimizer.config import OptimizeConfig
from pa800_optimizer.core.midi_io import extract_notes
from pa800_optimizer.profiles.registry import ProfileRegistry
from pa800_optimizer.optimizer import Optimizer
from pa800_optimizer.safety.rx_dnc import protect_note
from pa800_optimizer.verifier import verify


def nylon_dnc_legato_midi():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track)
    track.append(mido.MetaMessage('track_name',name='Nylon Guitar DNC',time=0));track.append(mido.Message('control_change',channel=0,control=0,value=121,time=0));track.append(mido.Message('control_change',channel=0,control=32,value=18,time=0));track.append(mido.Message('program_change',channel=0,program=24,time=0))
    track.append(mido.Message('note_on',channel=0,note=60,velocity=82,time=0));track.append(mido.Message('note_off',channel=0,note=60,velocity=0,time=96));track.append(mido.Message('note_on',channel=0,note=63,velocity=86,time=2));track.append(mido.Message('note_off',channel=0,note=63,velocity=0,time=96))
    return mid


def test_exact_dnc_slide_apply_inserts_verified_cc80_pulse():
    registry=ProfileRegistry();mid=nylon_dnc_legato_midi();before=copy.deepcopy(mid);contexts=build_contexts(mid,registry,'song');notes=extract_notes(mid)
    report,insertions=ArticulationDirector(registry).process(mid,contexts,notes,apply=True)
    assert report['exact_dnc_contexts']==1 and report['applied_triggers']==1
    assert insertions==[(0,0,98,80,127,63,0),(0,0,98,80,0,63,0)]
    assert verify(before,mid,authorized_articulation_insertions=insertions)['pass'] is True
    assert verify(before,mid)['pass'] is False


def test_suggest_policy_never_mutates_events():
    registry=ProfileRegistry();mid=nylon_dnc_legato_midi();before=copy.deepcopy(mid);contexts=build_contexts(mid,registry,'song');notes=extract_notes(mid)
    report,insertions=ArticulationDirector(registry).process(mid,contexts,notes,apply=False)
    assert report['applied_triggers']==0 and insertions==[]
    assert verify(before,mid)['pass'] is True
    assert report['contexts'][0]['suggestions'][0]['semantic']=='slide'
    assert report['contexts'][0]['suggestions'][0]['phrase_position']=='END'


def alto_sax_growl_midi():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track)
    track.append(mido.MetaMessage('track_name',name='Alto Sax DNC',time=0));track.append(mido.Message('control_change',channel=0,control=0,value=121,time=0));track.append(mido.Message('control_change',channel=0,control=32,value=12,time=0));track.append(mido.Message('program_change',channel=0,program=65,time=0));track.append(mido.Message('note_on',channel=0,note=65,velocity=100,time=0));track.append(mido.Message('note_off',channel=0,note=65,velocity=0,time=384));return mid


def test_expressive_growl_requires_hardware_e3_for_apply(tmp_path):
    registry=ProfileRegistry();mid=alto_sax_growl_midi();contexts=build_contexts(mid,registry,'song');notes=extract_notes(mid);report,insertions=ArticulationDirector(registry).process(mid,contexts,notes,apply=True)
    suggestion=report['contexts'][0]['suggestions'][0];assert suggestion['action']=='BLOCKED_REQUIRES_HARDWARE_E3' and not insertions
    evidence=tmp_path/'hardware.json';evidence.write_text('{"records":[{"kind":"articulation","source_address":[121,12,65],"control":81,"semantic":"growl_sax","approval":"safe-auto"}]}',encoding='utf-8')
    mid=alto_sax_growl_midi();contexts=build_contexts(mid,registry,'song');notes=extract_notes(mid);report,insertions=ArticulationDirector(registry,evidence).process(mid,contexts,notes,apply=True)
    assert report['applied_triggers']==1 and insertions and report['contexts'][0]['suggestions'][0]['evidence_level']=='E3'


def test_dnc_keyoff_noise_context_is_protected_from_generic_shaping():
    registry=ProfileRegistry();mid=nylon_dnc_legato_midi();contexts=build_contexts(mid,registry,'song');note=extract_notes(mid)[0];ctx=contexts[(0,0)];manual=registry.resolve_manual_dnc(121,18,24)
    protected,reason=protect_note(note,ctx,None,OptimizeConfig.for_mode('max'),manual)
    assert protected is True and reason=='dnc_articulation_integrity_guard'


def test_preserve_mode_blocks_explicit_articulation_apply():
    with tempfile.TemporaryDirectory() as directory:
        source=os.path.join(directory,'dnc.mid');output=os.path.join(directory,'dnc_out.mid');nylon_dnc_legato_midi().save(source)
        cfg=OptimizeConfig.for_mode('preserve');cfg.content_type='song';cfg.apply_articulation_triggers=True
        report=Optimizer(cfg).optimize(source,output)
        assert report.verifier['pass'] is True and report.articulations['applied_triggers']==0
        pulses=[(msg.control,msg.value) for track in mido.MidiFile(output).tracks for msg in track if msg.type=='control_change' and msg.control==80]
        assert pulses==[]


def test_optimizer_apply_policy_roundtrips_articulation_events():
    with tempfile.TemporaryDirectory() as directory:
        source=os.path.join(directory,'dnc.mid');output=os.path.join(directory,'dnc_out.mid');nylon_dnc_legato_midi().save(source)
        cfg=OptimizeConfig.for_mode('natural');cfg.content_type='song';cfg.apply_articulation_triggers=True
        report=Optimizer(cfg).optimize(source,output)
        assert report.verifier['pass'] is True and report.articulations['applied_triggers']==1
        pulses=[(msg.control,msg.value) for track in mido.MidiFile(output).tracks for msg in track if msg.type=='control_change' and msg.control==80]
        assert pulses==[(80,127),(80,0)]


def test_dnc_controller_state_is_scoped_per_midi_channel():
    mid=mido.MidiFile(type=0,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track)
    track.append(mido.Message('control_change',channel=0,control=80,value=127,time=0))
    track.append(mido.Message('pitchwheel',channel=0,pitch=2048,time=0))
    track.append(mido.Message('note_on',channel=1,note=60,velocity=90,time=0))
    track.append(mido.Message('note_on',channel=0,note=64,velocity=90,time=0))
    states=build_controller_states(mid)
    assert states[(0,2)]['cc80']==0 and states[(0,2)]['pitchbend']==0
    assert states[(0,3)]['cc80']==127 and states[(0,3)]['pitchbend']==2048