from types import SimpleNamespace
import mido

from pa800_optimizer.event_proposals import (
    generate_velocity_budget_proposals, arbitrate_event_proposals, commit_event_proposals,
    generate_mix_fx_proposals, arbitrate_controller_proposals, commit_controller_proposals,
)
from pa800_optimizer.core.midi_io import extract_notes
from pa800_optimizer.analysis.instrument_fingerprints import snapshot_instrument_state
from pa800_optimizer.config import OptimizeConfig
from pa800_optimizer.models import SoundIdentity, TrackContext


def _track_arb(channel=0):
    return {'pass':True,'tracks':[{'track':0,'channel':channel+1,'action':'NORMAL_CORRECT','ood_status':'NORMAL','execution_allowed':{'velocity':True,'timing':True,'gate':True,'pitch':False,'harmony':False}}]}


def _plan(channel=0):
    return {'tracks':[{'track':0,'channel':channel+1,'action':'NORMAL_CORRECT','ood_status':'NORMAL','allowed_dimensions':['velocity','timing','gate']}], 'summary':{}}


def test_velocity_budget_is_proposal_only_until_commit():
    mid=mido.MidiFile(type=1,ticks_per_beat=480); tr=mido.MidiTrack(); mid.tracks.append(tr)
    tr.append(mido.Message('note_on',channel=0,note=40,velocity=60,time=0));tr.append(mido.Message('note_off',channel=0,note=40,velocity=0,time=120))
    ctx=TrackContext(0,0,'BASS',SoundIdentity(121,0,0,'Bass','BASS'),family='BASS',content_type='song')
    contexts={(0,0):ctx};notes=extract_notes(mid);baseline=snapshot_instrument_state(mid,notes,contexts)
    # Simulate an upstream refiner that exceeded cumulative original budget.
    mid.tracks[0][0]=mid.tracks[0][0].copy(velocity=110);notes=extract_notes(mid)
    before=mid.tracks[0][0].velocity
    proposals,summary=generate_velocity_budget_proposals(mid,notes,contexts,baseline)
    assert summary['production_midi_mutated'] is False and proposals
    assert mid.tracks[0][0].velocity==before
    arb=arbitrate_event_proposals(proposals,_track_arb(),_plan());assert arb['pass']
    rep=SimpleNamespace(changes=[]);commit=commit_event_proposals(mid,arb,rep)
    assert commit['changes_committed']==1
    assert mid.tracks[0][0].velocity < before
    assert rep.changes[-1].kind=='velocity_budget'


def _mix_fixture():
    mid=mido.MidiFile(type=1,ticks_per_beat=192);tr=mido.MidiTrack();mid.tracks.append(tr)
    tr.append(mido.Message('control_change',channel=0,control=91,value=40,time=0))
    tr.append(mido.Message('control_change',channel=0,control=93,value=20,time=0))
    ctx=TrackContext(0,0,'SONG',SoundIdentity(121,3,0,'Bass','BASS'),family='BASS',content_type='song')
    contexts={(0,0):ctx}
    musical={'sections':[{'index':0,'label':'WHOLE','start_tick':0,'end_tick':2000,'evidence_level':'E1'}],
             'track_functions':[{'track':0,'channel':1,'function':'FOUNDATION_BASS'}],
             'ensemble_sections':[{'section_index':0,'parts':[{'track':0,'channel':1,'function':'FOUNDATION_BASS','density':2,'energy':90}],'focus':{'track':0,'channel':1},'masking_alerts':[],'focus_energy_margin_over_background':10}]}
    recommendations=[{'track':0,'channel':1,'fx':{'reverb':24,'chorus':6}}]
    return mid,contexts,musical,recommendations


def test_mix_fx_is_sandboxed_until_controller_commit():
    mid,contexts,musical,recommendations=_mix_fixture();cfg=OptimizeConfig.for_mode('live');cfg.mix_fx_policy='apply';cfg.apply_mix_fx_director=True
    before=[m.value for m in mid.tracks[0] if m.type=='control_change']
    proposals,report,channels,updates=generate_mix_fx_proposals(mid,contexts,musical,recommendations,cfg)
    assert report['proposal_mode'] is True and report['production_midi_mutated'] is False
    assert [m.value for m in mid.tracks[0] if m.type=='control_change']==before
    assert proposals and channels=={(0,0)}
    arb=arbitrate_controller_proposals(proposals);assert arb['pass']
    commit=commit_controller_proposals(mid,arb)
    assert commit['changes_committed']==len(proposals)
    assert [m.value for m in mid.tracks[0] if m.type=='control_change']!=before
