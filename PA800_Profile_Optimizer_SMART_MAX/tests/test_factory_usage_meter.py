from types import SimpleNamespace

from pa800_optimizer.analysis.factory_usage import build_factory_usage_meter,render_factory_usage_dashboard
from pa800_optimizer.config import OptimizeConfig
from pa800_optimizer.models import Change,NoteEvent,SoundIdentity,TrackContext


class RegistryStub:
    def resolve_drum_key(self,msb,lsb,program,note):
        return {'key':note} if (msb,lsb,program,note)==(120,0,0,36) else None

    def velocity_family_profile(self,family,role=None):
        return {'velocity':{'ideal_center':80}} if family=='BASS' else None

    def profile_completeness(self,profile):
        return {'completion_state':'COMPLETE_WITH_EXPLICIT_UNKNOWNS','unresolved':['audible_timbre_result']} if profile else None


def note(track,channel,pitch,occurrence=0,protected=False):
    return NoteEvent(track,channel,pitch,80,0,96,0,1,occurrence=occurrence,protected=protected)


def context(track,channel,family,role,identity):
    return TrackContext(track,channel,role,identity,family=family)


def test_usage_meter_classifies_every_note_once_and_counts_mutations():
    drum_id=SoundIdentity(120,0,0,'Kit',family='DRUM_KIT')
    bass_id=SoundIdentity(121,0,32,'Bass',family='BASS')
    unknown_id=SoundIdentity(1,2,3,'Unknown',family='UNKNOWN')
    contexts={
        (0,9):context(0,9,'DRUM_KIT','DRUM',drum_id),
        (1,8):context(1,8,'BASS','BASS',bass_id),
        (2,0):context(2,0,'UNKNOWN','SONG',unknown_id),
    }
    notes=[note(0,9,36),note(1,8,40),note(2,0,60)]
    profiles={(0,9):{'velocity':{'ideal_center':90}},(1,8):None,(2,0):None}
    changes=[Change(0,0,'velocity',80,82,'test',channel=9,note=36,occurrence=0)]
    meter=build_factory_usage_meter(notes,contexts,profiles,RegistryStub(),changes,OptimizeConfig.for_mode('live'))
    assert meter['pass']
    assert meter['notes_total']==3
    assert meter['invariants']['classification_sum']==3
    assert meter['classification_counts']=={'EXACT_KIT_KEY':1,'FAMILY_FALLBACK':1,'UNKNOWN':1}
    assert meter['stage_counts']['mutated']==1
    assert meter['stage_counts']['blocked']==1
    assert meter['contexts'][0]['profile_completeness']=='COMPLETE_WITH_EXPLICIT_UNKNOWNS'
    assert meter['contexts'][0]['explicit_unknowns']==1
    dashboard=render_factory_usage_dashboard(meter)
    assert 'FACTORY USAGE METER — PASS' in dashboard
    assert 'EXACT_KIT_KEY' in dashboard and 'DRUM_KIT' in dashboard
    assert 'blocked-note mutations=0' in dashboard
    assert 'COMPLETE_WITH_EXPLICIT_UNKNOWNS' in dashboard


def test_usage_meter_fails_if_a_blocked_note_was_mutated():
    identity=SoundIdentity(1,2,3,'Unknown',family='UNKNOWN')
    notes=[note(0,0,60)]
    contexts={(0,0):context(0,0,'UNKNOWN','SONG',identity)}
    changes=[Change(0,0,'velocity',80,90,'illegal',channel=0,note=60,occurrence=0)]
    meter=build_factory_usage_meter(notes,contexts,{(0,0):None},RegistryStub(),changes,OptimizeConfig.for_mode('live'))
    assert not meter['pass']
    assert meter['blocked_mutation_count']==1