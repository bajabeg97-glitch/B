import copy
from types import SimpleNamespace
import mido

from pa800_optimizer.event_proposals import generate_refiner_proposals, arbitrate_event_proposals, commit_event_proposals, arbitrate_controller_proposals, commit_controller_proposals
from pa800_optimizer.core.midi_io import extract_notes
from pa800_optimizer.analysis.intent import classify_intents
from pa800_optimizer.config import OptimizeConfig

class Identity:
    def __init__(self,name='Test',msb=0,lsb=0,program=0):
        self.name=name;self.msb=msb;self.lsb=lsb;self.program=program;self.conflict=False
    def address(self): return (self.msb,self.lsb,self.program)

class Registry:
    data_dir='.'
    def resolve_drum_key(self,*a,**k): return None
    def velocity_family_profile(self,*a,**k): return None


def _mid(channel=10, velocities=(100,90,80,70), with_cc11=False):
    mid=mido.MidiFile(ticks_per_beat=480);tr=mido.MidiTrack();mid.tracks.append(tr)
    if with_cc11: tr.append(mido.Message('control_change',channel=channel,control=11,value=80,time=0))
    for i,v in enumerate(velocities):
        tr.append(mido.Message('note_on',channel=channel,note=60+i,velocity=v,time=120 if i else 0))
        tr.append(mido.Message('note_off',channel=channel,note=60+i,velocity=0,time=120))
    return mid


def _ctx(channel=10,role='PERC',family='PERCUSSION'):
    return {(0,channel):SimpleNamespace(track_index=0,channel=channel,role=role,family=family,element=None,cv=None,identity=Identity())}


def _plan(channel=10):
    return {'tracks':[{'track':0,'channel':channel+1,'action':'NORMAL_CORRECT','ood_status':'NORMAL','allowed_dimensions':['velocity','timing','gate']}], 'summary':{}}


def _track_arb(channel=10):
    return {'pass':True,'tracks':[{'track':0,'channel':channel+1,'action':'NORMAL_CORRECT','ood_status':'NORMAL','execution_allowed':{'velocity':True,'timing':True,'gate':True,'pitch':False,'harmony':False}}], 'accepted_proposals':3,'rejected_proposals':0}


def test_refiner_sandbox_does_not_mutate_production_and_baja_is_proposed():
    mid=_mid();before=bytes(mid.save(file=None)) if False else [(m.type,getattr(m,'velocity',None),getattr(m,'value',None)) for m in mid.tracks[0]]
    notes=extract_notes(mid);classify_intents(notes,_ctx(),mid.ticks_per_beat)
    for n in notes:n.protected=False
    cfg=OptimizeConfig.for_mode('max');cfg.enable_velocity_conductor=False;cfg.enable_performance_director=False;cfg.apply_performance_director=False;cfg.apply_baja_stage_profile=True
    vp,cp,summary=generate_refiner_proposals(mid,notes,_ctx(),{},Registry(),{'track_functions':[],'sections':[]},cfg)
    after=[(m.type,getattr(m,'velocity',None),getattr(m,'value',None)) for m in mid.tracks[0]]
    assert before==after
    assert cp==[]
    assert summary['production_midi_mutated'] is False
    assert vp and all(r['source']=='PERFORMANCE_REFINER_PIPELINE' for r in vp)
    assert all(r['final_change_kind']=='baja_percussion_40pct' for r in vp)


def test_refiner_baja_commit_is_atomic_and_preserves_note_identity():
    mid=_mid();notes=extract_notes(mid);classify_intents(notes,_ctx(),mid.ticks_per_beat)
    for n in notes:n.protected=False
    cfg=OptimizeConfig.for_mode('max');cfg.enable_velocity_conductor=False;cfg.enable_performance_director=False;cfg.apply_performance_director=False;cfg.apply_baja_stage_profile=True
    vp,_,_=generate_refiner_proposals(mid,notes,_ctx(),{},Registry(),{'track_functions':[],'sections':[]},cfg)
    arb=arbitrate_event_proposals(vp,_track_arb(),_plan());assert arb['pass']
    rep=SimpleNamespace(changes=[]);commit=commit_event_proposals(mid,arb,rep)
    out=extract_notes(mid)
    assert [n.note for n in out]==[60,61,62,63]
    assert [n.velocity for n in out]==[40,36,32,28]
    assert commit['changes_committed']==4
    assert all(c.kind=='baja_percussion_40pct' for c in rep.changes)


def test_controller_proposals_require_explicit_commit():
    # Unit-test controller transaction itself; Performance Director evidence
    # generation is covered by its dedicated tests.
    mid=_mid(channel=0,velocities=(90,),with_cc11=True)
    original=mid.tracks[0][0].value
    proposals=[{'event_key':[0,0,11,0],'track':0,'channel':0,'control':11,'occurrence':0,'source':'PERFORMANCE_DIRECTOR_EXPRESSION','dimension':'controller','old_value':80,'new_value':84,'delta':4,'tick':0}]
    arb=arbitrate_controller_proposals(proposals);assert arb['pass']
    assert mid.tracks[0][0].value==original
    result=commit_controller_proposals(mid,arb)
    assert result['changes_committed']==1
    assert mid.tracks[0][0].value==84
