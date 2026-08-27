import mido

from pa800_optimizer.config import OptimizeConfig
from pa800_optimizer.musician_workflow import build_musician_workflow,render_dashboard
from pa800_optimizer.optimizer import Optimizer


def test_musical_presets_express_bounded_musician_policies():
    groove=OptimizeConfig.for_musical_preset('groove_first')
    assert groove.musical_preset=='groove_first' and groove.timing_strength<=.12 and groove.velocity_random_strength<=.20
    vocal=OptimizeConfig.for_musical_preset('vocal_backing')
    assert vocal.vocal_friendly_mode and not vocal.apply_performance_director and vocal.mix_fx_policy=='shadow'
    live=OptimizeConfig.for_musical_preset('live_stage')
    assert live.live_performance_mode and live.smart_policy_override=='suggest' and live.velocity_conductor_max_delta<=24
    creative=OptimizeConfig.for_musical_preset('creative_preview')
    assert creative.creative_policy=='preview' and not creative.apply_articulation_triggers


def test_dashboard_combines_roles_sections_groove_harmony_and_creative_preview():
    cfg=OptimizeConfig.for_musical_preset('creative_preview')
    context={'track_functions':[{'track':0,'channel':1,'function':'LEAD'},{'track':1,'channel':10,'function':'FOUNDATION_DRUM'}]}
    understanding={'groove':{'relationships':[{'relationship':'LOCKED'}]},'arrangement':{'sections':[{'trajectory_from_previous':'START'},{'trajectory_from_previous':'BUILD'}]},'interaction':{'relationships':[{'relationship':'CALL_RESPONSE_CANDIDATE'}]},'harmony':{'chord_count':2,'voice_leading':[{}],'tonal_center':{'name':'C'}}}
    result=build_musician_workflow(cfg,context,understanding);text=render_dashboard(result)
    assert result['schema']=='PA800_MUSICIAN_WORKFLOW_V1' and result['creative_mutations']==0
    assert result['cards']['creative_tools']['status']=='PREVIEW'
    assert all(not row['apply_authority'] for row in result['cards']['creative_tools']['proposals'])
    assert 'Groove Preserver: ACTIVE' in text and 'Harmonic Context: ACTIVE' in text


def test_vocal_friendly_preserves_inferred_foreground_note_events(tmp_path):
    source=tmp_path/'vocal.mid';output=tmp_path/'vocal-out.mid';report=tmp_path/'vocal.json'
    mid=mido.MidiFile(type=1,ticks_per_beat=192)
    lead=mido.MidiTrack();bass=mido.MidiTrack();mid.tracks.extend([lead,bass])
    lead.extend([mido.MetaMessage('track_name',name='Lead Melody',time=0),mido.Message('program_change',channel=0,program=73,time=0)])
    bass.extend([mido.MetaMessage('track_name',name='Bass',time=0),mido.Message('program_change',channel=1,program=33,time=0)])
    for index in range(8):
        lead.extend([mido.Message('note_on',channel=0,note=72+index%3,velocity=50+index*3,time=48),mido.Message('note_off',channel=0,note=72+index%3,velocity=0,time=96)])
        bass.extend([mido.Message('note_on',channel=1,note=36+index%2,velocity=65+index,time=48),mido.Message('note_off',channel=1,note=36+index%2,velocity=0,time=96)])
    mid.save(source);before=mido.MidiFile(source)
    cfg=OptimizeConfig.for_musical_preset('vocal_backing');cfg.content_type='song'
    result=Optimizer(cfg).optimize(source,output,report);after=mido.MidiFile(output)
    before_lead=[(msg.type,getattr(msg,'note',None),getattr(msg,'velocity',None),msg.time) for msg in before.tracks[0] if msg.type in ('note_on','note_off')]
    after_lead=[(msg.type,getattr(msg,'note',None),getattr(msg,'velocity',None),msg.time) for msg in after.tracks[0] if msg.type in ('note_on','note_off')]
    assert before_lead==after_lead
    assert result.musician_workflow['cards']['vocal_friendly']['protected_foreground_contexts']>=1
    assert not [change for change in result.changes if change.track==0]


def test_original_preserve_preset_is_strict_byte_preserve(tmp_path):
    source=tmp_path/'original.mid';output=tmp_path/'original-out.mid'
    mid=mido.MidiFile(type=1,ticks_per_beat=192);track=mido.MidiTrack();mid.tracks.append(track)
    track.extend([mido.Message('note_on',channel=0,note=60,velocity=64,time=0),mido.Message('note_off',channel=0,note=60,velocity=0,time=192)]);mid.save(source)
    result=Optimizer(OptimizeConfig.for_musical_preset('original_preserve')).optimize(source,output)
    assert source.read_bytes()==output.read_bytes() and result.musician_workflow['preset']=='original_preserve'