import json
import mido

from pa800_optimizer.config import OptimizeConfig
from pa800_optimizer.mix_fx_director import run_mix_fx_director
from pa800_optimizer.models import SoundIdentity,TrackContext


def fixture(values91=(60,),values93=(40,),family='PIANO',function='HARMONIC_COMP',rx=False):
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track)
    for index,value in enumerate(values91):track.append(mido.Message('control_change',channel=0,control=91,value=value,time=0 if index==0 else 192))
    for index,value in enumerate(values93):track.append(mido.Message('control_change',channel=0,control=93,value=value,time=0 if index==0 else 192))
    ctx=TrackContext(0,0,'BASS' if family=='BASS' else 'SONG',SoundIdentity(121,3,0,family.title(),family,rx_named=rx),family=family,content_type='song')
    context={'sections':[{'index':0,'label':'WHOLE_SONG','start_tick':0,'end_tick':2000,'evidence_level':'E1'}],'track_functions':[{'track':0,'channel':1,'function':function}],'ensemble_sections':[{'section_index':0,'parts':[{'track':0,'channel':1,'function':function,'density':2,'energy':90}],'focus':{'track':0,'channel':1},'masking_alerts':[],'focus_energy_margin_over_background':10}]}
    recommendation=[{'track':0,'channel':1,'fx':{'reverb':24,'chorus':6}}]
    return mid,{(0,0):ctx},context,recommendation


def values(mid,control):return [msg.value for track in mid.tracks for msg in track if msg.type=='control_change' and msg.control==control]


def test_shadow_mode_is_analyzer_only():
    mid,contexts,context,recommendations=fixture();before=values(mid,91);cfg=OptimizeConfig.for_mode('live');cfg.mix_fx_policy='shadow'
    report,channels,updates=run_mix_fx_director(mid,contexts,context,recommendations,cfg)
    assert report['policy']=='shadow' and report['mutations']==0 and not channels and values(mid,91)==before
    assert report['contexts'][0]['sections'] and updates[(0,0)]['fx_apply_status']=='shadow_only'


def test_non_e3_apply_is_dry_only_and_preserves_contour():
    mid,contexts,context,recommendations=fixture((40,70,90),(20,30),'BASS','FOUNDATION_BASS');before=values(mid,91);cfg=OptimizeConfig.for_mode('live');cfg.mix_fx_policy='apply';cfg.apply_mix_fx_director=True
    report,channels,_=run_mix_fx_director(mid,contexts,context,recommendations,cfg);after=values(mid,91)
    assert report['mutations']>0 and channels=={(0,0)} and all(a<=b for a,b in zip(after,before))
    assert [b-a for a,b in zip(before,before[1:])]==[b-a for a,b in zip(after,after[1:])]
    assert report['contexts'][0]['apply_status']=='applied_bounded_dry_guard'


def test_positive_depth_requires_e3_hardware_approval(tmp_path):
    mid,contexts,context,recommendations=fixture((5,),(2,),'SYNTH_PAD','PAD_BACKGROUND');cfg=OptimizeConfig.for_mode('live');cfg.mix_fx_policy='apply';cfg.apply_mix_fx_director=True
    report,channels,_=run_mix_fx_director(mid,contexts,context,recommendations,cfg)
    assert report['mutations']==0 and not channels and values(mid,91)==[5]
    evidence=tmp_path/'fx.json';evidence.write_text(json.dumps({'records':[{'kind':'fx','source_address':[121,3,0],'family':'SYNTH_PAD','scope':'section','approval':'safe-auto'}]}),encoding='utf-8')
    mid,contexts,context,recommendations=fixture((5,),(2,),'SYNTH_PAD','PAD_BACKGROUND');cfg.hardware_evidence_path=str(evidence)
    report,channels,_=run_mix_fx_director(mid,contexts,context,recommendations,cfg)
    assert report['mutations']==2 and channels=={(0,0)} and values(mid,91)[0]>5
    assert report['contexts'][0]['section_depth_authority'] is True and report['contexts'][0]['evidence_level']=='E3'


def test_rx_context_is_never_rewritten():
    mid,contexts,context,recommendations=fixture((90,),(50,),'GUITAR','LEAD',rx=True);cfg=OptimizeConfig.for_mode('live');cfg.mix_fx_policy='apply';cfg.apply_mix_fx_director=True
    report,channels,_=run_mix_fx_director(mid,contexts,context,recommendations,cfg)
    assert report['mutations']==0 and not channels and report['contexts'][0]['apply_status']=='blocked_sensitive_unknown_or_conflict'