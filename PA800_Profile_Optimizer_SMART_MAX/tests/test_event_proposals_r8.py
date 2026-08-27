import copy
import mido
from pa800_optimizer.core.midi_io import extract_notes
from pa800_optimizer.models import OptimizationReport
from pa800_optimizer.event_proposals import arbitrate_event_proposals, commit_event_proposals


def _mid():
    mid=mido.MidiFile(type=1,ticks_per_beat=192)
    tr=mido.MidiTrack();mid.tracks.append(tr)
    tr.append(mido.Message('note_on',channel=0,note=60,velocity=70,time=0))
    tr.append(mido.Message('note_off',channel=0,note=60,velocity=0,time=96))
    tr.append(mido.MetaMessage('end_of_track',time=0))
    return mid


def _track_arb():
    return {'tracks':[{'track':0,'channel':1,'execution_allowed':{'velocity':True,'timing':True,'gate':True,'pitch':False,'harmony':False}}]}


def test_event_arbiter_prefers_neural_gate_but_keeps_independent_dimensions():
    base={'event_key':[0,0,60,0],'track':0,'channel':0,'note':60,'occurrence':0,'on_index':0,'off_index':1,'protected':False,
          'old_velocity':70,'new_velocity':82,'old_onset':0,'new_onset':0,'old_duration':96,'new_duration':96,'reasons':[]}
    proposals=[
        {**base,'dimension':'velocity','source':'VELOCITY_ENGINE','delta':12},
        {**base,'dimension':'timing','source':'NEURAL_TIMING_ENGINE','delta':4,'new_onset':4},
        {**base,'dimension':'gate','source':'GATE_ENGINE','delta':8,'new_duration':104},
        {**base,'dimension':'gate','source':'NEURAL_TIMING_ENGINE_DURATION','delta':5,'new_duration':101},
    ]
    out=arbitrate_event_proposals(proposals,_track_arb())
    assert out['pass']
    accepted={(row['dimension'],row['source']) for row in out['accepted']}
    assert ('velocity','VELOCITY_ENGINE') in accepted
    assert ('timing','NEURAL_TIMING_ENGINE') in accepted
    assert ('gate','NEURAL_TIMING_ENGINE_DURATION') in accepted
    assert any(row['rejection_reason']=='lower_priority_proposal' and row['source']=='GATE_ENGINE' for row in out['rejected'])


def test_shared_commit_composes_onset_and_duration_atomically():
    mid=_mid();original=copy.deepcopy(mid);rep=OptimizationReport('in','out')
    base={'event_key':[0,0,60,0],'track':0,'channel':0,'note':60,'occurrence':0,'on_index':0,'off_index':1,'protected':False,
          'old_velocity':70,'new_velocity':82,'old_onset':0,'new_onset':4,'old_duration':96,'new_duration':101,'reasons':[]}
    arb={'pass':True,'accepted':[
        {**base,'dimension':'velocity','source':'VELOCITY_ENGINE','delta':12},
        {**base,'dimension':'timing','source':'NEURAL_TIMING_ENGINE','delta':4},
        {**base,'dimension':'gate','source':'NEURAL_TIMING_ENGINE_DURATION','delta':5},
    ]}
    result=commit_event_proposals(mid,arb,rep)
    note=extract_notes(mid)[0]
    old=extract_notes(original)[0]
    assert (old.velocity,old.onset,old.duration)==(70,0,96)
    assert (note.velocity,note.onset,note.duration)==(82,4,101)
    assert result['changes_committed']==3
    assert [c.kind for c in rep.changes]==['velocity','timing','gate']
    assert rep.changes[-1].old==100 and rep.changes[-1].new==105


def test_hard_preserve_track_rejects_every_proposal():
    arb={'tracks':[{'track':0,'channel':1,'execution_allowed':{'velocity':False,'timing':False,'gate':False,'pitch':False,'harmony':False}}]}
    row={'event_key':[0,0,60,0],'track':0,'channel':0,'note':60,'occurrence':0,'on_index':0,'off_index':1,'protected':False,
         'old_velocity':70,'new_velocity':90,'old_onset':0,'new_onset':0,'old_duration':96,'new_duration':96,
         'dimension':'velocity','source':'VELOCITY_ENGINE','delta':20,'reasons':[]}
    out=arbitrate_event_proposals([row],arb)
    assert out['pass'] and out['accepted_count']==0 and out['rejected_count']==1
